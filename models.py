from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class HighlightSegment(BaseModel):
    """Represents a single highlight segment identified by the AI"""
    start_time: float
    end_time: float
    clip_description: str


class ClipAnalysis(BaseModel):
    """Full analysis of a video clip"""
    highlights: List[HighlightSegment]
    source_path: str
    analyzed_at: datetime = Field(default_factory=datetime.now)
    total_duration: float


class ClipInfo(BaseModel):
    """Information about a video clip"""
    id: Optional[int] = None
    name: str
    path: str
    analysis: Optional[ClipAnalysis] = None
    used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SelectedHighlight(BaseModel):
    """A highlight segment selected for the final compilation"""
    source_path: str  # Current path to the video file
    original_clip_path: str  # Original path when the clip was analyzed
    clip_id: Optional[int] = None  # Database ID of the clip
    start_time: float
    end_time: float
    duration: float
    description: str


class CompilationPlan(BaseModel):
    """Plan for the final video compilation"""
    highlights: List[SelectedHighlight]
    total_duration: float
    target_duration: float 