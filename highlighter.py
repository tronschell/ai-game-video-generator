import json
import os
import random
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from loguru import logger

from db import ClipDatabase
from models import HighlightSegment, ClipAnalysis, SelectedHighlight, CompilationPlan
from agent import process_video_with_agent
from video import list_video_files, get_video_duration


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def get_clip_sort_key(video_path: str) -> float:
    """Get the sort key for a video clip (modification time)"""
    try:
        return os.path.getmtime(video_path)
    except OSError:
        logger.warning(f"Could not get modification time for {video_path}, using 0")
        return 0


class HighlightCompiler:
    def __init__(
        self,
        clips_folder: str = "E:\\Game Recordings\\Counter-strike 2",
        db_path: str = "clips.db",
        output_length_minutes: float = 10.0,
        include_used_clips: bool = False
    ):
        self.clips_folder = clips_folder
        self.db = ClipDatabase(db_path)
        self.target_duration = output_length_minutes * 60  # convert to seconds
        self.include_used_clips = include_used_clips
    
    def scan_clips_folder(self) -> List[str]:
        """Scan the clips folder for video files and add them to the database"""
        logger.info(f"Scanning clips folder: {self.clips_folder}")
        video_files = list_video_files(self.clips_folder)
        
        # Sort video files by modification time (newest first)
        video_files.sort(key=get_clip_sort_key, reverse=True)
        logger.info(f"Found {len(video_files)} clips, sorted by newest first")
        
        for video_path in video_files:
            clip_name = os.path.basename(video_path)
            # Add modification time to the database for future reference
            mod_time = datetime.fromtimestamp(get_clip_sort_key(video_path))
            self.db.add_clip(clip_name, video_path, {"recorded_at": mod_time.isoformat()})
        
        return video_files
    
    async def analyze_clips(self, clips_to_analyze: Optional[List[str]] = None) -> List[ClipAnalysis]:
        """Analyze clips using the AI agent"""
        if clips_to_analyze is None:
            # Get all clips from DB that need analysis
            all_clips = self.db.get_all_clips() if self.include_used_clips else self.db.get_unused_clips()
            
            # Sort clips by recorded_at if available, otherwise by path
            def get_clip_time(clip: Dict[str, Any]) -> float:
                if clip.get("metadata", {}).get("recorded_at"):
                    try:
                        dt = datetime.fromisoformat(clip["metadata"]["recorded_at"])
                        return dt.timestamp()
                    except (ValueError, TypeError):
                        pass
                return get_clip_sort_key(clip["path"])
            
            all_clips.sort(key=get_clip_time, reverse=True)
            clips_to_analyze = [clip["path"] for clip in all_clips if not clip["analysis"]]
            
            logger.info(f"Found {len(clips_to_analyze)} clips to analyze, sorted by newest first")
        
        analyses = []
        for clip_path in clips_to_analyze:
            logger.info(f"Analyzing clip: {clip_path}")
            
            try:
                # Get clip info from database
                clip = self.db.get_clip_by_path(clip_path)
                if not clip:
                    clip_name = os.path.basename(clip_path)
                    mod_time = datetime.fromtimestamp(get_clip_sort_key(clip_path))
                    clip_id = self.db.add_clip(clip_name, clip_path, {"recorded_at": mod_time.isoformat()})
                else:
                    clip_id = clip["id"]
                
                # Process with agent
                analysis = await process_video_with_agent(clip_path)
                
                # Update database
                self.db.update_clip_analysis(clip_id, analysis.model_dump())
                
                analyses.append(analysis)
                
                # Save analysis as JSON file (for reference)
                json_path = os.path.splitext(clip_path)[0] + "_analysis.json"
                with open(json_path, 'w') as f:
                    json.dump(analysis.model_dump(), f, indent=2, default=str, cls=DateTimeEncoder)
                
                logger.success(f"Analysis complete for {clip_path}, saved to {json_path}")
                
            except Exception as e:
                logger.error(f"Error analyzing clip {clip_path}: {e}")
        
        return analyses
    
    def _calculate_highlight_duration(self, highlight: HighlightSegment) -> float:
        """Calculate the duration of a highlight segment"""
        return highlight.end_time - highlight.start_time
    
    def plan_compilation(self) -> CompilationPlan:
        """Create a plan for the highlight compilation"""
        logger.info(f"Planning compilation with target duration of {self.target_duration}s")
        
        # Get all analyzed clips
        clips = self.db.get_all_clips() if self.include_used_clips else self.db.get_unused_clips()
        clips_with_analysis = [clip for clip in clips if clip["analysis"] is not None]
        
        if not clips_with_analysis:
            logger.error("No analyzed clips available for compilation")
            raise ValueError("No analyzed clips available")
        
        # Sort clips by recorded_at if available
        def get_clip_time(clip: Dict[str, Any]) -> float:
            if clip.get("metadata", {}).get("recorded_at"):
                try:
                    dt = datetime.fromisoformat(clip["metadata"]["recorded_at"])
                    return dt.timestamp()
                except (ValueError, TypeError):
                    pass
                return get_clip_sort_key(clip["path"])
        
        clips_with_analysis.sort(key=get_clip_time, reverse=True)
        logger.info(f"Found {len(clips_with_analysis)} analyzed clips, sorted by newest first")
        
        # Extract all highlights
        all_highlights = []
        for clip in clips_with_analysis:
            analysis = clip["analysis"]
            source_path = clip["path"]
            
            for highlight in analysis["highlights"]:
                duration = highlight["end_time"] - highlight["start_time"]
                all_highlights.append(
                    SelectedHighlight(
                        source_path=source_path,
                        original_clip_path=source_path,  # Store the original path
                        clip_id=clip["id"],  # Store the database ID
                        start_time=highlight["start_time"],
                        end_time=highlight["end_time"],
                        duration=duration,
                        description=highlight["clip_description"]
                    )
                )
        
        # Sort by duration (shorter clips first)
        all_highlights.sort(key=lambda h: h.duration)
        
        # Select highlights to meet target duration
        selected_highlights = []
        current_duration = 0.0
        
        # First pass: include highlights until we reach target duration
        i = 0
        while i < len(all_highlights) and current_duration < self.target_duration:
            highlight = all_highlights[i]
            
            # Check if adding this highlight would exceed target by too much
            if current_duration + highlight.duration > self.target_duration * 1.1:
                # Skip if it would make us go over by more than 10%
                i += 1
                continue
            
            selected_highlights.append(highlight)
            current_duration += highlight.duration
            
            # Remove from consideration
            all_highlights.pop(i)
        
        # If we don't have enough highlights, add more
        if current_duration < self.target_duration * 0.9:
            logger.warning(f"Not enough highlights to reach target duration. Current: {current_duration}s")
            
            # Add more highlights if available
            remaining_highlights = sorted(all_highlights, key=lambda h: random.random())
            
            for highlight in remaining_highlights:
                if current_duration >= self.target_duration:
                    break
                
                selected_highlights.append(highlight)
                current_duration += highlight.duration
        
        # Sort by source path and start time for efficient processing
        selected_highlights.sort(key=lambda h: (h.source_path, h.start_time))
        
        # Create compilation plan
        plan = CompilationPlan(
            highlights=selected_highlights,
            total_duration=current_duration,
            target_duration=self.target_duration
        )
        
        logger.success(f"Compilation plan created with {len(selected_highlights)} highlights")
        logger.info(f"Total duration: {current_duration}s / Target: {self.target_duration}s")
        
        return plan
    
    def mark_clips_as_used(self, plan: CompilationPlan) -> None:
        """Mark all clips used in a compilation as used"""
        source_paths = set(highlight.source_path for highlight in plan.highlights)
        
        for path in source_paths:
            clip = self.db.get_clip_by_path(path)
            if clip:
                self.db.mark_clip_as_used(clip["id"])
        
        logger.info(f"Marked {len(source_paths)} clips as used") 