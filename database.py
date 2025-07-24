import sqlite3
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
import os
import threading
from contextlib import contextmanager

@dataclass
class FileMetadata:
    """Data class for file metadata"""
    filename: str
    upload_timestamp: datetime
    row_count: int
    parquet_path: Optional[str]
    status: str
    id: Optional[int] = None

class DatabaseManager:
    """Manages SQLite database operations for file metadata with thread safety"""
    
    def __init__(self, db_path: str = "metadata.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.init_database()
    
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def init_database(self):
        """Initialize the database and create tables if they don't exist"""
        with self._lock:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS file_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT NOT NULL,
                        upload_timestamp TEXT NOT NULL,
                        row_count INTEGER NOT NULL,
                        parquet_path TEXT,
                        status TEXT NOT NULL CHECK (status IN ('Processing', 'Done', 'Error')),
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_filename 
                    ON file_metadata(filename)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_status 
                    ON file_metadata(status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_upload_timestamp 
                    ON file_metadata(upload_timestamp)
                """)
                
                conn.commit()
    
    def insert_metadata(self, metadata: FileMetadata) -> int:
        """Insert file metadata and return the generated ID"""
        with self._lock:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO file_metadata 
                    (filename, upload_timestamp, row_count, parquet_path, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    metadata.filename,
                    metadata.upload_timestamp.isoformat(),
                    metadata.row_count,
                    metadata.parquet_path,
                    metadata.status
                ))
                conn.commit()
                return cursor.lastrowid
    
    def get_all_metadata(self) -> List[FileMetadata]:
        """Retrieve all file metadata entries ordered by upload timestamp"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, filename, upload_timestamp, row_count, parquet_path, status
                FROM file_metadata
                ORDER BY upload_timestamp DESC
            """)
            
            results = []
            for row in cursor.fetchall():
                metadata = FileMetadata(
                    id=row['id'],
                    filename=row['filename'],
                    upload_timestamp=datetime.fromisoformat(row['upload_timestamp']),
                    row_count=row['row_count'],
                    parquet_path=row['parquet_path'],
                    status=row['status']
                )
                results.append(metadata)
            
            return results
    
    def update_status(self, file_id: int, new_status: str) -> bool:
        """Update the status of a file and return success status"""
        valid_statuses = ['Processing', 'Done', 'Error']
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        
        with self._lock:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE file_metadata 
                    SET status = ?
                    WHERE id = ?
                """, (new_status, file_id))
                conn.commit()
                return cursor.rowcount > 0
    
    def get_metadata_by_id(self, file_id: int) -> Optional[FileMetadata]:
        """Get metadata for a specific file by ID"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, filename, upload_timestamp, row_count, parquet_path, status
                FROM file_metadata
                WHERE id = ?
            """, (file_id,))
            
            row = cursor.fetchone()
            if row:
                return FileMetadata(
                    id=row['id'],
                    filename=row['filename'],
                    upload_timestamp=datetime.fromisoformat(row['upload_timestamp']),
                    row_count=row['row_count'],
                    parquet_path=row['parquet_path'],
                    status=row['status']
                )
            return None
    
    def get_metadata_by_filename(self, filename: str) -> List[FileMetadata]:
        """Get all metadata entries for a specific filename"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, filename, upload_timestamp, row_count, parquet_path, status
                FROM file_metadata
                WHERE filename = ?
                ORDER BY upload_timestamp DESC
            """, (filename,))
            
            results = []
            for row in cursor.fetchall():
                metadata = FileMetadata(
                    id=row['id'],
                    filename=row['filename'],
                    upload_timestamp=datetime.fromisoformat(row['upload_timestamp']),
                    row_count=row['row_count'],
                    parquet_path=row['parquet_path'],
                    status=row['status']
                )
                results.append(metadata)
            
            return results
    
    def delete_metadata(self, file_id: int) -> bool:
        """Delete metadata entry by ID and return success status"""
        with self._lock:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM file_metadata WHERE id = ?", (file_id,))
                conn.commit()
                return cursor.rowcount > 0
    
    def get_files_by_status(self, status: str) -> List[FileMetadata]:
        """Get all files with a specific status"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, filename, upload_timestamp, row_count, parquet_path, status
                FROM file_metadata
                WHERE status = ?
                ORDER BY upload_timestamp DESC
            """, (status,))
            
            results = []
            for row in cursor.fetchall():
                metadata = FileMetadata(
                    id=row['id'],
                    filename=row['filename'],
                    upload_timestamp=datetime.fromisoformat(row['upload_timestamp']),
                    row_count=row['row_count'],
                    parquet_path=row['parquet_path'],
                    status=row['status']
                )
                results.append(metadata)
            
            return results
    
    def get_statistics(self) -> dict:
        """Get database statistics"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Total files
            cursor.execute("SELECT COUNT(*) FROM file_metadata")
            total_files = cursor.fetchone()[0]
            
            # Files by status
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM file_metadata 
                GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())
            
            # Total rows processed
            cursor.execute("SELECT SUM(row_count) FROM file_metadata WHERE status = 'Done'")
            total_rows = cursor.fetchone()[0] or 0
            
            return {
                "total_files": total_files,
                "status_counts": status_counts,
                "total_rows_processed": total_rows
            } 