"""
Database manager with PostgreSQL and SQLite support using SQLAlchemy
"""

import sqlite3
from datetime import datetime
from typing import List, Optional
import os
import threading
from contextlib import contextmanager

try:
    from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, Session
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

from ..models.file_metadata import FileMetadata
from .config import get_settings

if HAS_SQLALCHEMY:
    Base = declarative_base()

    class FileMetadataDB(Base):
        """SQLAlchemy model for file metadata"""
        __tablename__ = "file_metadata"
        
        id = Column(Integer, primary_key=True, index=True)
        filename = Column(String(255), nullable=False, index=True)
        upload_timestamp = Column(DateTime, nullable=False, index=True)
        row_count = Column(Integer, nullable=False)
        parquet_path = Column(Text, nullable=True)
        status = Column(String(50), nullable=False, default="Processing", index=True)

class ProductionDatabaseManager:
    """Production database manager with PostgreSQL and SQLite support"""
    
    def __init__(self):
        self.settings = get_settings()
        self.engine = None
        self.SessionLocal = None
        self.use_sqlalchemy = False
        self._lock = threading.Lock()
        self.init_database()
    
    def init_database(self):
        """Initialize the database and create tables if they don't exist"""
        try:
            database_url = self.settings.computed_database_url
            
            if HAS_SQLALCHEMY and (database_url.startswith("postgresql://") or self.settings.environment == "production"):
                self._init_sqlalchemy(database_url)
            else:
                self._init_sqlite()
                
        except Exception as e:
            print(f"Database initialization failed, falling back to SQLite: {e}")
            self._init_sqlite()
    
    def _init_sqlalchemy(self, database_url: str):
        """Initialize SQLAlchemy for PostgreSQL"""
        if database_url.startswith("postgresql://"):
            # PostgreSQL configuration with SSL support (for Neon, etc.)
            connect_args = {}
            if "sslmode=require" in database_url:
                connect_args["sslmode"] = "require"
            
            self.engine = create_engine(
                database_url,
                pool_pre_ping=True,
                pool_recycle=300,
                pool_size=5,
                max_overflow=10,
                connect_args=connect_args,
                echo=False
            )
        else:
            # SQLite with SQLAlchemy
            self.engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                echo=False
            )
        
        self.SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=self.engine
        )
        
        # Create tables
        Base.metadata.create_all(bind=self.engine)
        self.use_sqlalchemy = True
        print(f"✅ Database initialized with SQLAlchemy: {database_url}")
    
    def _init_sqlite(self):
        """Initialize plain SQLite as fallback"""
        self.db_path = self.settings.database_path
        self.use_sqlalchemy = False
        
        with self._get_sqlite_connection() as conn:
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
        print("✅ Database initialized with SQLite")
    
    @contextmanager
    def _get_sqlite_connection(self):
        """Context manager for SQLite connections"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        if self.use_sqlalchemy:
            session = self.SessionLocal()
            try:
                yield session
                session.commit()
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()
        else:
            with self._get_sqlite_connection() as conn:
                yield conn
    
    def _db_to_model(self, db_record) -> FileMetadata:
        """Convert database record to FileMetadata dataclass"""
        if self.use_sqlalchemy:
            return FileMetadata(
                id=db_record.id,
                filename=db_record.filename,
                upload_timestamp=db_record.upload_timestamp,
                row_count=db_record.row_count,
                parquet_path=db_record.parquet_path,
                status=db_record.status
            )
        else:
            return FileMetadata(
                id=db_record['id'],
                filename=db_record['filename'],
                upload_timestamp=datetime.fromisoformat(db_record['upload_timestamp']),
                row_count=db_record['row_count'],
                parquet_path=db_record['parquet_path'],
                status=db_record['status']
            )
    
    def insert_metadata(self, metadata: FileMetadata) -> int:
        """Insert file metadata and return the generated ID"""
        with self._lock:
            with self.get_session() as session:
                if self.use_sqlalchemy:
                    db_record = FileMetadataDB(
                        filename=metadata.filename,
                        upload_timestamp=metadata.upload_timestamp,
                        row_count=metadata.row_count,
                        parquet_path=metadata.parquet_path,
                        status=metadata.status
                    )
                    session.add(db_record)
                    session.flush()  # To get the ID
                    return db_record.id
                else:
                    cursor = session.cursor()
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
                    return cursor.lastrowid
    
    def get_all_metadata(self) -> List[FileMetadata]:
        """Retrieve all file metadata entries ordered by upload timestamp"""
        with self.get_session() as session:
            if self.use_sqlalchemy:
                records = session.query(FileMetadataDB).order_by(
                    FileMetadataDB.upload_timestamp.desc()
                ).all()
                return [self._db_to_model(record) for record in records]
            else:
                cursor = session.cursor()
                cursor.execute("""
                    SELECT id, filename, upload_timestamp, row_count, parquet_path, status
                    FROM file_metadata
                    ORDER BY upload_timestamp DESC
                """)
                return [self._db_to_model(row) for row in cursor.fetchall()]
    
    def update_status(self, file_id: int, new_status: str) -> bool:
        """Update the status of a file and return success status"""
        valid_statuses = ['Processing', 'Done', 'Error']
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        
        with self._lock:
            with self.get_session() as session:
                if self.use_sqlalchemy:
                    record = session.query(FileMetadataDB).filter(
                        FileMetadataDB.id == file_id
                    ).first()
                    if record:
                        record.status = new_status
                        return True
                    return False
                else:
                    cursor = session.cursor()
                    cursor.execute("""
                        UPDATE file_metadata 
                        SET status = ?
                        WHERE id = ?
                    """, (new_status, file_id))
                    return cursor.rowcount > 0
    
    def get_metadata_by_id(self, file_id: int) -> Optional[FileMetadata]:
        """Get metadata for a specific file by ID"""
        with self.get_session() as session:
            if self.use_sqlalchemy:
                record = session.query(FileMetadataDB).filter(
                    FileMetadataDB.id == file_id
                ).first()
                return self._db_to_model(record) if record else None
            else:
                cursor = session.cursor()
                cursor.execute("""
                    SELECT id, filename, upload_timestamp, row_count, parquet_path, status
                    FROM file_metadata
                    WHERE id = ?
                """, (file_id,))
                row = cursor.fetchone()
                return self._db_to_model(row) if row else None
    
    def get_metadata_by_filename(self, filename: str) -> List[FileMetadata]:
        """Get all metadata entries for a specific filename"""
        with self.get_session() as session:
            if self.use_sqlalchemy:
                records = session.query(FileMetadataDB).filter(
                    FileMetadataDB.filename == filename
                ).order_by(FileMetadataDB.upload_timestamp.desc()).all()
                return [self._db_to_model(record) for record in records]
            else:
                cursor = session.cursor()
                cursor.execute("""
                    SELECT id, filename, upload_timestamp, row_count, parquet_path, status
                    FROM file_metadata
                    WHERE filename = ?
                    ORDER BY upload_timestamp DESC
                """, (filename,))
                return [self._db_to_model(row) for row in cursor.fetchall()]
    
    def delete_metadata(self, file_id: int) -> bool:
        """Delete metadata entry by ID and return success status"""
        with self._lock:
            with self.get_session() as session:
                if self.use_sqlalchemy:
                    record = session.query(FileMetadataDB).filter(
                        FileMetadataDB.id == file_id
                    ).first()
                    if record:
                        session.delete(record)
                        return True
                    return False
                else:
                    cursor = session.cursor()
                    cursor.execute("DELETE FROM file_metadata WHERE id = ?", (file_id,))
                    return cursor.rowcount > 0
    
    def get_files_by_status(self, status: str) -> List[FileMetadata]:
        """Get all files with a specific status"""
        with self.get_session() as session:
            if self.use_sqlalchemy:
                records = session.query(FileMetadataDB).filter(
                    FileMetadataDB.status == status
                ).order_by(FileMetadataDB.upload_timestamp.desc()).all()
                return [self._db_to_model(record) for record in records]
            else:
                cursor = session.cursor()
                cursor.execute("""
                    SELECT id, filename, upload_timestamp, row_count, parquet_path, status
                    FROM file_metadata
                    WHERE status = ?
                    ORDER BY upload_timestamp DESC
                """, (status,))
                return [self._db_to_model(row) for row in cursor.fetchall()]
    
    def get_statistics(self) -> dict:
        """Get database statistics"""
        with self.get_session() as session:
            if self.use_sqlalchemy:
                from sqlalchemy import func
                
                # Total files
                total_files = session.query(func.count(FileMetadataDB.id)).scalar()
                
                # Files by status
                status_query = session.query(
                    FileMetadataDB.status, 
                    func.count(FileMetadataDB.id)
                ).group_by(FileMetadataDB.status).all()
                status_counts = dict(status_query)
                
                # Total rows processed
                total_rows = session.query(
                    func.sum(FileMetadataDB.row_count)
                ).filter(FileMetadataDB.status == 'Done').scalar() or 0
                
            else:
                cursor = session.cursor()
                
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