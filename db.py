import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger


class ClipDatabase:
    def __init__(self, db_path: str = "clips.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database and create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create clips table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            analysis TEXT,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def add_clip(self, name: str, path: str, analysis: Optional[Dict[str, Any]] = None) -> int:
        """Add a new clip to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        analysis_json = json.dumps(analysis) if analysis else None
        
        try:
            cursor.execute(
                "INSERT INTO clips (name, path, analysis) VALUES (?, ?, ?)",
                (name, path, analysis_json)
            )
            clip_id = cursor.lastrowid
            conn.commit()
            logger.debug(f"Added clip {name} to database with ID {clip_id}")
            return clip_id
        except sqlite3.IntegrityError:
            logger.debug(f"Clip with path {path} already exists in database")
            cursor.execute("SELECT id FROM clips WHERE path = ?", (path,))
            clip_id = cursor.fetchone()[0]
            return clip_id
        finally:
            conn.close()
    
    def update_clip_analysis(self, clip_id: int, analysis: Dict[str, Any]) -> None:
        """Update the analysis for a clip"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE clips SET analysis = ? WHERE id = ?",
            (json.dumps(analysis), clip_id)
        )
        
        conn.commit()
        conn.close()
        logger.debug(f"Updated analysis for clip ID {clip_id}")
    
    def mark_clip_as_used(self, clip_id: int) -> None:
        """Mark a clip as used with current timestamp"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE clips SET used_at = ? WHERE id = ?",
            (datetime.now().isoformat(), clip_id)
        )
        
        conn.commit()
        conn.close()
        logger.debug(f"Marked clip ID {clip_id} as used")
    
    def get_unused_clips(self) -> List[Dict[str, Any]]:
        """Get all clips that haven't been used yet"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM clips WHERE used_at IS NULL")
        clips = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        logger.debug(f"Found {len(clips)} unused clips")
        
        # Parse the JSON analysis
        for clip in clips:
            if clip['analysis']:
                clip['analysis'] = json.loads(clip['analysis'])
        
        return clips
    
    def get_all_clips(self) -> List[Dict[str, Any]]:
        """Get all clips in the database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM clips")
        clips = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        logger.debug(f"Found {len(clips)} total clips")
        
        # Parse the JSON analysis
        for clip in clips:
            if clip['analysis']:
                clip['analysis'] = json.loads(clip['analysis'])
        
        return clips
    
    def get_clip_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Get a clip by its path"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM clips WHERE path = ?", (path,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return None
        
        clip = dict(row)
        if clip['analysis']:
            clip['analysis'] = json.loads(clip['analysis'])
        
        return clip 