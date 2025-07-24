from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
import os
import pandas as pd
import asyncio
from datetime import datetime
import aiofiles

from ..dependencies import get_current_user
from ...core.database import DatabaseManager
from ...models.file_metadata import FileMetadata

router = APIRouter(tags=["File Operations"])

# Initialize managers
db_manager = DatabaseManager()

# Ensure directories exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("parquet", exist_ok=True)

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload CSV file and convert to Parquet
    
    - Accepts only CSV files
    - Returns "Processing" status immediately for files with data
    - Returns "Error" status for empty files
    - Updates to "Done" after 3-second delay for successful files
    """
    
    # Validate file type
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed"
        )
    
    # Check if file is empty
    if file.size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )
    
    try:
        # Save uploaded file
        upload_path = f"uploads/{file.filename}"
        async with aiofiles.open(upload_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Read CSV and validate
        df = pd.read_csv(upload_path)
        row_count = len(df)
        
        # Determine status based on row count
        if row_count == 0:
            status_value = "Error"
            parquet_path = None
        else:
            status_value = "Processing"
            # Convert to Parquet
            parquet_filename = file.filename.replace('.csv', '.parquet')
            parquet_path = f"parquet/{parquet_filename}"
            df.to_parquet(parquet_path, index=False)
            
    except pd.errors.EmptyDataError:
        status_value = "Error"
        row_count = 0
        parquet_path = None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )
    
    # Store metadata in database
    metadata = FileMetadata(
        filename=file.filename,
        upload_timestamp=datetime.now(),
        row_count=row_count,
        parquet_path=parquet_path,
        status=status_value
    )
    
    file_id = db_manager.insert_metadata(metadata)
    
    # Prepare response data
    response_data = {
        "id": file_id,
        "filename": file.filename,
        "upload_timestamp": metadata.upload_timestamp.isoformat(),
        "row_count": row_count,
        "status": status_value,
        "parquet_path": parquet_path
    }
    
    # Simulate processing delay for files with rows > 0
    if row_count > 0:
        # Update status to "Done" after 3 seconds (background task)
        asyncio.create_task(update_status_after_delay(file_id, 3))
    
    return response_data

async def update_status_after_delay(file_id: int, delay_seconds: int):
    """Background task to update file status after delay"""
    await asyncio.sleep(delay_seconds)
    db_manager.update_status(file_id, "Done")

@router.get("/files")
async def get_files(current_user: dict = Depends(get_current_user)):
    """
    Get all file metadata
    
    Returns a list of all uploaded files with their metadata including:
    - ID, filename, upload timestamp
    - Row count, processing status
    - Path to converted Parquet file
    """
    files = db_manager.get_all_metadata()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "upload_timestamp": f.upload_timestamp.isoformat(),
            "row_count": f.row_count,
            "status": f.status,
            "parquet_path": f.parquet_path
        }
        for f in files
    ]

@router.get("/files/{file_id}")
async def get_file_by_id(
    file_id: int, 
    current_user: dict = Depends(get_current_user)
):
    """Get metadata for a specific file by ID"""
    file_metadata = db_manager.get_metadata_by_id(file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return {
        "id": file_metadata.id,
        "filename": file_metadata.filename,
        "upload_timestamp": file_metadata.upload_timestamp.isoformat(),
        "row_count": file_metadata.row_count,
        "status": file_metadata.status,
        "parquet_path": file_metadata.parquet_path
    }

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int, 
    current_user: dict = Depends(get_current_user)
):
    """Delete a file and its metadata"""
    file_metadata = db_manager.get_metadata_by_id(file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Delete physical files
    try:
        if os.path.exists(f"uploads/{file_metadata.filename}"):
            os.remove(f"uploads/{file_metadata.filename}")
        if file_metadata.parquet_path and os.path.exists(file_metadata.parquet_path):
            os.remove(file_metadata.parquet_path)
    except Exception as e:
        # Log error but continue with metadata deletion
        print(f"Error deleting physical files: {e}")
    
    # Delete metadata
    db_manager.delete_metadata(file_id)
    
    return {"message": "File deleted successfully"} 