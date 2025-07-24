import pandas as pd
import os
import asyncio
from typing import Tuple, Optional
from pathlib import Path
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileProcessor:
    """Handles CSV file processing and Parquet conversion"""
    
    def __init__(self, upload_dir: str = "uploads", parquet_dir: str = "parquet"):
        self.upload_dir = Path(upload_dir)
        self.parquet_dir = Path(parquet_dir)
        
        # Ensure directories exist
        self.upload_dir.mkdir(exist_ok=True)
        self.parquet_dir.mkdir(exist_ok=True)
    
    async def process_csv_file(self, file_path: str, filename: str) -> Tuple[int, str, Optional[str]]:
        """
        Process a CSV file and convert to Parquet
        
        Returns:
            - row_count: Number of rows in the CSV
            - status: Processing status ('Processing', 'Error', 'Done')
            - parquet_path: Path to the converted Parquet file (if successful)
        """
        try:
            # Read CSV file
            df = pd.read_csv(file_path)
            row_count = len(df)
            
            if row_count == 0:
                logger.warning(f"CSV file {filename} contains 0 rows")
                return 0, "Error", None
            
            # Generate Parquet filename
            parquet_filename = filename.replace('.csv', '.parquet')
            parquet_path = self.parquet_dir / parquet_filename
            
            # Convert to Parquet
            df.to_parquet(parquet_path, index=False)
            
            logger.info(f"Successfully converted {filename} to Parquet: {row_count} rows")
            return row_count, "Processing", str(parquet_path)
            
        except pd.errors.EmptyDataError:
            logger.error(f"CSV file {filename} is empty or has no data")
            return 0, "Error", None
        except pd.errors.ParserError as e:
            logger.error(f"Error parsing CSV file {filename}: {e}")
            return 0, "Error", None
        except Exception as e:
            logger.error(f"Unexpected error processing {filename}: {e}")
            return 0, "Error", None
    
    def validate_csv_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate a CSV file
        
        Returns:
            - is_valid: Whether the file is valid
            - message: Validation message
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return False, "File does not exist"
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return False, "File is empty"
            
            # Try to read the first few rows to validate CSV format
            df = pd.read_csv(file_path, nrows=5)
            
            return True, "File is valid"
            
        except pd.errors.EmptyDataError:
            return False, "CSV file contains no data"
        except pd.errors.ParserError:
            return False, "Invalid CSV format"
        except Exception as e:
            return False, f"Error validating file: {str(e)}"
    
    def get_csv_info(self, file_path: str) -> dict:
        """
        Get information about a CSV file
        
        Returns:
            Dictionary with file information
        """
        try:
            df = pd.read_csv(file_path)
            
            return {
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": df.columns.tolist(),
                "file_size": os.path.getsize(file_path),
                "dtypes": df.dtypes.to_dict(),
                "memory_usage": df.memory_usage(deep=True).sum(),
                "has_null_values": df.isnull().any().any()
            }
        except Exception as e:
            logger.error(f"Error getting CSV info: {e}")
            return {"error": str(e)}
    
    def clean_up_files(self, csv_path: str, parquet_path: Optional[str] = None):
        """Clean up uploaded and processed files"""
        try:
            if os.path.exists(csv_path):
                os.remove(csv_path)
                logger.info(f"Removed CSV file: {csv_path}")
            
            if parquet_path and os.path.exists(parquet_path):
                os.remove(parquet_path)
                logger.info(f"Removed Parquet file: {parquet_path}")
                
        except Exception as e:
            logger.error(f"Error cleaning up files: {e}")
    
    async def process_with_delay(self, file_path: str, filename: str, delay_seconds: int = 3) -> Tuple[int, str, Optional[str]]:
        """
        Process a file with a simulated delay
        
        This method simulates the processing time for demonstration purposes
        """
        # First, do the actual processing
        row_count, initial_status, parquet_path = await self.process_csv_file(file_path, filename)
        
        if initial_status == "Processing":
            # Simulate processing delay
            await asyncio.sleep(delay_seconds)
            return row_count, "Done", parquet_path
        
        return row_count, initial_status, parquet_path
    
    def get_storage_statistics(self) -> dict:
        """Get storage statistics for uploads and parquet directories"""
        def get_dir_size(directory: Path) -> int:
            """Calculate total size of all files in directory"""
            total_size = 0
            try:
                for file_path in directory.rglob('*'):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
            except Exception as e:
                logger.error(f"Error calculating directory size: {e}")
            return total_size
        
        def count_files(directory: Path, extension: str = None) -> int:
            """Count files in directory, optionally filtered by extension"""
            try:
                if extension:
                    return len(list(directory.glob(f'*{extension}')))
                else:
                    return len([f for f in directory.iterdir() if f.is_file()])
            except Exception:
                return 0
        
        return {
            "upload_directory": {
                "path": str(self.upload_dir),
                "total_size_bytes": get_dir_size(self.upload_dir),
                "csv_files": count_files(self.upload_dir, '.csv'),
                "total_files": count_files(self.upload_dir)
            },
            "parquet_directory": {
                "path": str(self.parquet_dir),
                "total_size_bytes": get_dir_size(self.parquet_dir),
                "parquet_files": count_files(self.parquet_dir, '.parquet'),
                "total_files": count_files(self.parquet_dir)
            }
        } 