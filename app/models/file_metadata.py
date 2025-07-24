from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class FileMetadata:
    """Data class for file metadata"""
    filename: str
    upload_timestamp: datetime
    row_count: int
    parquet_path: Optional[str]
    status: str
    id: Optional[int] = None 