#!/usr/bin/env python
import os
import sys
import logging
import tempfile
import subprocess
import json
import time
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
import asyncio
import traceback

# WhisperX imports
import torch
import whisperx

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SubtitleGenerator:
    def __init__(self, model_name: str = "large"):
        """
        Initialize the subtitle generator with a WhisperX model.
        
        Args:
            model_name: The Whisper model size to use for transcription (tiny, base, small, medium, large, large-v2)
        """
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if torch.cuda.is_available() else "int8"
        self.asr_model = None
        self.align_model = None
        self.align_metadata = None
        self.diarize_model = None
        
    def _initialize_asr_model(self):
        """Initialize the WhisperX ASR model if not already initialized."""
        if self.asr_model is None:
            logger.info(f"Initializing WhisperX ASR model: {self.model_name}")
            try:
                # Load the ASR model
                self.asr_model = whisperx.load_model(
                    self.model_name,
                    self.device,
                    compute_type=self.compute_type,
                    language=None  # Auto-detect language
                )
                logger.info("WhisperX ASR model initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing WhisperX ASR model: {str(e)}")
                raise
    
    def _initialize_align_model(self, language_code: str):
        """Initialize the alignment model for the detected language."""
        if self.align_model is None or language_code != getattr(self, 'current_language', None):
            logger.info(f"Initializing WhisperX alignment model for language: {language_code}")
            try:
                self.align_model, self.align_metadata = whisperx.load_align_model(
                    language_code=language_code,
                    device=self.device
                )
                self.current_language = language_code
                logger.info("WhisperX alignment model initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing WhisperX alignment model: {str(e)}")
                raise
    
    def _initialize_diarize_model(self):
        """Initialize the diarization model if not already initialized."""
        if self.diarize_model is None:
            logger.info("Initializing WhisperX diarization model")
            try:
                self.diarize_model = whisperx.DiarizationPipeline(
                    device=self.device,
                    use_auth_token=None  # Set your HF token here if needed
                )
                logger.info("WhisperX diarization model initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing WhisperX diarization model: {str(e)}")
                raise
    
    def transcribe_audio(self, audio_path: str, diarize: bool = False, min_speakers: Optional[int] = None, max_speakers: Optional[int] = None) -> Dict:
        """
        Transcribe an audio file using WhisperX with optional speaker diarization.
        
        Args:
            audio_path: Path to the audio file
            diarize: Whether to perform speaker diarization
            min_speakers: Minimum number of speakers (optional, for diarization)
            max_speakers: Maximum number of speakers (optional, for diarization)
            
        Returns:
            Dictionary containing the transcription results with word-level timestamps
        """
        logger.info(f"Transcribing audio: {audio_path}")
        
        try:
            # Load audio
            audio = whisperx.load_audio(audio_path)
            
            # Ensure ASR model is initialized
            self._initialize_asr_model()
            
            # Transcribe with Whisper
            start_time = time.time()
            result = self.asr_model.transcribe(audio, batch_size=16)
            initial_transcribe_time = time.time() - start_time
            logger.info(f"Initial transcription completed in {initial_transcribe_time:.2f} seconds")
            
            # Get the detected language
            language_code = result["language"]
            logger.info(f"Detected language: {language_code}")
            
            # Initialize alignment model for the detected language
            self._initialize_align_model(language_code)
            
            # Align the transcription to get accurate word-level timestamps
            align_start_time = time.time()
            result = whisperx.align(
                result["segments"],
                self.align_model,
                self.align_metadata,
                audio,
                self.device,
                return_char_alignments=False
            )
            align_time = time.time() - align_start_time
            logger.info(f"Alignment completed in {align_time:.2f} seconds")
            
            # Perform speaker diarization if requested
            if diarize:
                self._initialize_diarize_model()
                
                diarize_start_time = time.time()
                
                diarize_kwargs = {}
                if min_speakers is not None:
                    diarize_kwargs["min_speakers"] = min_speakers
                if max_speakers is not None:
                    diarize_kwargs["max_speakers"] = max_speakers
                
                diarize_segments = self.diarize_model(audio, **diarize_kwargs)
                result = whisperx.assign_word_speakers(diarize_segments, result)
                
                diarize_time = time.time() - diarize_start_time
                logger.info(f"Diarization completed in {diarize_time:.2f} seconds")
            
            total_time = time.time() - start_time
            logger.info(f"Total processing completed in {total_time:.2f} seconds")
            
            return result
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _split_into_chunks(self, text: str, max_words: int) -> List[str]:
        """
        Split text into chunks with a maximum number of words per chunk.
        
        Args:
            text: The text to split
            max_words: Maximum number of words per chunk
            
        Returns:
            List of text chunks
        """
        words = text.split()
        return [' '.join(words[i:i+max_words]) for i in range(0, len(words), max_words)]

    def _format_time(self, seconds: float) -> str:
        """
        Format time in SRT format (HH:MM:SS,mmm).
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Time formatted for SRT
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:06.3f}".replace(".", ",")

    def generate_srt(self, result: Dict, max_words_per_line: int, include_speaker: bool = False) -> List[str]:
        """
        Generate SRT format subtitles from WhisperX transcription.
        
        Args:
            result: Transcription result from WhisperX
            max_words_per_line: Maximum number of words per subtitle line
            include_speaker: Whether to include speaker labels in subtitles
            
        Returns:
            List of SRT format subtitle entries
        """
        if not result or "segments" not in result:
            logger.warning("No segments found in transcription result")
            return []
        
        srt_lines = []
        subtitle_index = 1
        
        # Group words by segments for better rendering
        for segment in result["segments"]:
            segment_speaker = segment.get("speaker", "SPEAKER")
            segment_text = segment.get("text", "").strip()
            
            # Skip empty segments
            if not segment_text:
                continue
            
            # Check if we have word-level timestamps
            if "words" in segment and segment["words"]:
                # Process words with their timestamps
                current_line_words = []
                current_line_start = None
                
                for word_data in segment["words"]:
                    word = word_data.get("word", "").strip()
                    word_speaker = word_data.get("speaker", segment_speaker)
                    
                    if not word:
                        continue
                    
                    # Initialize start time for new line
                    if current_line_start is None:
                        current_line_start = word_data.get("start", 0)
                    
                    current_line_words.append(word)
                    
                    # When we reach max words or end of segment, create a subtitle entry
                    if len(current_line_words) >= max_words_per_line:
                        line_text = " ".join(current_line_words)
                        line_end = word_data.get("end", 0)
                        
                        if include_speaker and word_speaker:
                            line_text = f"[{word_speaker}] {line_text}"
                        
                        srt_entry = [
                            str(subtitle_index),
                            f"{self._format_time(current_line_start)} --> {self._format_time(line_end)}",
                            line_text,
                            ""  # Empty line between entries
                        ]
                        
                        srt_lines.extend(srt_entry)
                        subtitle_index += 1
                        
                        # Reset for next line
                        current_line_words = []
                        current_line_start = None
                
                # Handle any remaining words in the last line
                if current_line_words:
                    line_text = " ".join(current_line_words)
                    line_end = segment.get("end", 0)
                    
                    if include_speaker and segment_speaker:
                        line_text = f"[{segment_speaker}] {line_text}"
                    
                    srt_entry = [
                        str(subtitle_index),
                        f"{self._format_time(current_line_start)} --> {self._format_time(line_end)}",
                        line_text,
                        ""  # Empty line between entries
                    ]
                    
                    srt_lines.extend(srt_entry)
                    subtitle_index += 1
            else:
                # No word-level timestamps, process the whole segment
                segment_start = segment.get("start", 0)
                segment_end = segment.get("end", 0)
                
                # Split text into chunks with max_words_per_line
                text_chunks = self._split_into_chunks(segment_text, max_words_per_line)
                
                # Calculate time per chunk
                if len(text_chunks) > 1:
                    time_per_chunk = (segment_end - segment_start) / len(text_chunks)
                else:
                    time_per_chunk = segment_end - segment_start
                
                # Generate SRT entries for each chunk
                for i, chunk_text in enumerate(text_chunks):
                    chunk_start = segment_start + (i * time_per_chunk)
                    chunk_end = chunk_start + time_per_chunk
                    
                    if include_speaker and segment_speaker:
                        chunk_text = f"[{segment_speaker}] {chunk_text}"
                    
                    srt_entry = [
                        str(subtitle_index),
                        f"{self._format_time(chunk_start)} --> {self._format_time(chunk_end)}",
                        chunk_text,
                        ""  # Empty line between entries
                    ]
                    
                    srt_lines.extend(srt_entry)
                    subtitle_index += 1
        
        return srt_lines

    def create_subtitle_file(self, 
                           video_path: str, 
                           max_words_per_line: int, 
                           output_srt_path: Optional[str] = None,
                           diarize: bool = False,
                           min_speakers: Optional[int] = None,
                           max_speakers: Optional[int] = None,
                           include_speaker: bool = False) -> str:
        """
        Create an SRT subtitle file for a video using WhisperX.
        
        Args:
            video_path: Path to the video file
            max_words_per_line: Maximum number of words per subtitle line
            output_srt_path: Path to save the SRT file (optional)
            diarize: Whether to perform speaker diarization
            min_speakers: Minimum number of speakers (optional, for diarization)
            max_speakers: Maximum number of speakers (optional, for diarization)
            include_speaker: Whether to include speaker labels in subtitles
            
        Returns:
            Path to the generated SRT file
        """
        if output_srt_path is None:
            # Generate output path based on video path
            video_path_obj = Path(video_path)
            output_srt_path = str(video_path_obj.with_suffix('.srt'))
        
        try:
            # Transcribe the audio with WhisperX
            audio_path = video_path  # WhisperX will extract audio internally
            result = self.transcribe_audio(
                audio_path, 
                diarize=diarize,
                min_speakers=min_speakers, 
                max_speakers=max_speakers
            )
            
            # Generate SRT format subtitles
            srt_lines = self.generate_srt(
                result, 
                max_words_per_line,
                include_speaker=include_speaker and diarize
            )
            
            # Write SRT file
            with open(output_srt_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_lines))
            
            logger.info(f"Generated SRT subtitle file: {output_srt_path}")
            return output_srt_path
        except Exception as e:
            logger.error(f"Error creating subtitle file: {str(e)}")
            raise
            
    def add_subtitles_to_ffmpeg_cmd(self, ffmpeg_cmd: List[str], srt_path: str) -> List[str]:
        """
        Modify ffmpeg command to add subtitles.
        
        Args:
            ffmpeg_cmd: Original ffmpeg command list
            srt_path: Path to the SRT subtitle file
            
        Returns:
            Modified ffmpeg command with subtitle options
        """
        output_index = len(ffmpeg_cmd) - 1
        
        # Convert to absolute POSIX path for consistency
        posix_path = Path(srt_path).resolve().as_posix()
        # Escape the colon for Windows drive letters for FFmpeg filter syntax
        ffmpeg_filter_path = posix_path.replace(':', '\\:')

        # Construct the video filter string for subtitles with styling
        # Note: No extra single quotes around ffmpeg_filter_path for filename value
        vf_filter = f"subtitles=filename={ffmpeg_filter_path}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF,BackColour=&H00000000,OutlineColour=&H80000000,BorderStyle=1,Outline=1,Shadow=1'"
        
        subtitle_options = [
            '-vf', vf_filter
        ]
        
        return ffmpeg_cmd[:output_index] + subtitle_options + ffmpeg_cmd[output_index:]

def cleanup_temp_files():
    """
    This function used to clean up temporary filter files.
    It's kept for backwards compatibility but no longer needed since
    we're using direct filter_complex instead of temporary files.
    """
    # No longer needed as we're not creating temporary files anymore
    pass

async def process_video_with_subtitles(video_path: str, is_short: bool = False, diarize: bool = False) -> Tuple[str, str]:
    """
    Process a video to generate subtitles.
    
    Args:
        video_path: Path to the video file
        is_short: Whether the video is a short-form video
        diarize: Whether to perform speaker diarization
        
    Returns:
        Tuple of (video_path, srt_path)
    """
    max_words = 3 if is_short else 6
    
    generator = SubtitleGenerator()
    srt_path = generator.create_subtitle_file(
        video_path, 
        max_words, 
        diarize=diarize,
        include_speaker=diarize and not is_short  # Only include speaker labels for long-form videos
    )
    
    return video_path, srt_path

def generate_subtitles_for_video(video_path: str, is_short: bool = False, diarize: bool = False) -> str:
    """
    Generate subtitles for a video file.
    
    Args:
        video_path: Path to the video file
        is_short: Whether the video is a short-form video
        diarize: Whether to perform speaker diarization
        
    Returns:
        Path to the generated SRT file
    """
    max_words = 3 if is_short else 6
    
    generator = SubtitleGenerator()
    return generator.create_subtitle_file(
        video_path, 
        max_words,
        diarize=diarize,
        include_speaker=diarize and not is_short  # Only include speaker labels for long-form videos
    )

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate SRT subtitles for a video using WhisperX")
    parser.add_argument("video_path", help="Path to the video file")
    parser.add_argument("--short", action="store_true", help="Format subtitles for short-form video (3 words per line)")
    parser.add_argument("--output", help="Output SRT file path (optional)")
    parser.add_argument("--model", default="large", help="WhisperX model size (tiny, base, small, medium, large, large-v2)")
    parser.add_argument("--diarize", action="store_true", help="Perform speaker diarization")
    parser.add_argument("--min-speakers", type=int, help="Minimum number of speakers (for diarization)")
    parser.add_argument("--max-speakers", type=int, help="Maximum number of speakers (for diarization)")
    parser.add_argument("--include-speaker", action="store_true", help="Include speaker labels in subtitles")
    
    args = parser.parse_args()
    
    try:
        generator = SubtitleGenerator(model_name=args.model)
        srt_path = generator.create_subtitle_file(
            args.video_path, 
            max_words_per_line=3 if args.short else 6,
            output_srt_path=args.output,
            diarize=args.diarize,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers,
            include_speaker=args.include_speaker
        )
        print(f"Generated SRT file: {srt_path}")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
    finally:
        # Clean up any temporary files
        cleanup_temp_files() 