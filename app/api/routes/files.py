from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
import os
import pandas as pd
import numpy as np
import asyncio
from datetime import datetime
import aiofiles
from typing import Optional, Any, Dict, List, Union
import json

from ..dependencies import get_current_user
from ...core.database import DatabaseManager
from ...core.database_postgres import ProductionDatabaseManager
from ...core.storage import storage_service
from ...core.config import get_settings
from ...models.file_metadata import FileMetadata

def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize data structures to be JSON serializable
    Handles NaN, infinity, complex types, and other non-JSON compliant values
    """
    if pd.isna(obj):
        return None
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return [sanitize_for_json(item) for item in obj.tolist()]
    elif isinstance(obj, dict):
        return {key: sanitize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, str):
        return str(obj)
    elif obj is None:
        return None
    else:
        # For any other type, try to convert to string
        try:
            return str(obj)
        except:
            return None

def df_to_json_safe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convert DataFrame to JSON-safe list of dictionaries
    Handles all data types that might cause JSON serialization issues
    """
    # Replace problematic values
    df_clean = df.copy()
    
    # Handle different data types
    for col in df_clean.columns:
        if df_clean[col].dtype == 'object':
            # For object columns, handle mixed types
            df_clean[col] = df_clean[col].apply(sanitize_for_json)
        elif pd.api.types.is_numeric_dtype(df_clean[col]):
            # For numeric columns, handle NaN and infinity
            df_clean[col] = df_clean[col].apply(sanitize_for_json)
        elif pd.api.types.is_datetime64_any_dtype(df_clean[col]):
            # Convert datetime to ISO string
            df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d %H:%M:%S').fillna(None)
        else:
            # For any other type, apply general sanitization
            df_clean[col] = df_clean[col].apply(sanitize_for_json)
    
    # Convert to records
    records = df_clean.to_dict('records')
    
    # Final sanitization pass
    return [sanitize_for_json(record) for record in records]

def read_csv_robust(file_path: str) -> pd.DataFrame:
    """
    Robust CSV reader that handles various encodings, delimiters, and formats
    """
    try:
        # Try standard UTF-8 first
        return pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            # Try Latin-1 encoding
            return pd.read_csv(file_path, encoding='latin1')
        except Exception:
            try:
                # Try Windows encoding
                return pd.read_csv(file_path, encoding='cp1252')
            except Exception:
                # Try ISO encoding
                return pd.read_csv(file_path, encoding='iso-8859-1')
    except pd.errors.ParserError:
        try:
            # Try semicolon delimiter
            return pd.read_csv(file_path, sep=';', encoding='utf-8')
        except Exception:
            try:
                # Try tab delimiter
                return pd.read_csv(file_path, sep='\t', encoding='utf-8')
            except Exception:
                try:
                    # Try pipe delimiter
                    return pd.read_csv(file_path, sep='|', encoding='utf-8')
                except Exception:
                    # Last resort: let pandas auto-detect
                    return pd.read_csv(file_path, sep=None, engine='python', encoding='utf-8')
    except Exception:
        # Final fallback with minimal assumptions
        return pd.read_csv(file_path, sep=None, engine='python', encoding='utf-8', on_bad_lines='skip')

router = APIRouter(tags=["File Operations"])

# Initialize managers
# Initialize database manager (production-ready)
settings = get_settings()
if settings.environment == "production" or settings.is_production:
    db_manager = ProductionDatabaseManager()
else:
    db_manager = DatabaseManager()

# Storage service (works with both local and R2 storage)
storage = storage_service

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
        # Read file content
        content = await file.read()
        
        # Save uploaded file to storage (local or R2)
        upload_path = await storage.save_file(content, file.filename, "csv")
        
        # Read CSV and validate (with robust error handling)
        if settings.should_use_cloud_storage:
            # For R2 storage, read from cloud and create temp file for processing
            csv_content = await storage.read_file(upload_path)
            temp_path = f"temp_{file.filename}"
            async with aiofiles.open(temp_path, 'wb') as f:
                await f.write(csv_content)
            df = read_csv_robust(temp_path)
            os.remove(temp_path)  # Clean up temp file
        else:
            # For local storage, read directly
            df = read_csv_robust(upload_path)
        
        row_count = len(df)
        
        # Determine status based on row count
        if row_count == 0:
            status_value = "Error"
            parquet_path = None
        else:
            status_value = "Processing"
            # Convert to Parquet
            parquet_filename = file.filename.replace('.csv', '.parquet')
            
            # Create parquet file
            import io
            parquet_buffer = io.BytesIO()
            df.to_parquet(parquet_buffer, index=False)
            parquet_content = parquet_buffer.getvalue()
            
            # Save parquet to storage (local or R2)
            parquet_path = await storage.save_file(parquet_content, parquet_filename, "parquet")
            
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
        "parquet_path": parquet_path,
        "storage_type": "cloud" if settings.should_use_cloud_storage else "local",
        "storage_info": {
            "csv_path": upload_path,
            "parquet_path": parquet_path,
            "storage_backend": "r2" if settings.should_use_cloud_storage else "local_filesystem"
        }
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

@router.get("/files/{file_id}/data")
async def get_file_data(
    file_id: int,
    limit: Optional[int] = Query(100, description="Number of rows to return"),
    offset: Optional[int] = Query(0, description="Number of rows to skip"),
    format: Optional[str] = Query("parquet", description="Data format: 'csv' or 'parquet'"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the actual data content from a processed file
    
    - Returns data in JSON format for frontend consumption
    - Supports pagination with limit/offset
    - Can return original CSV or transformed Parquet data
    """
    file_metadata = db_manager.get_metadata_by_id(file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if file_metadata.status != "Done":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is not ready. Status: {file_metadata.status}"
        )
    
    try:
        if format.lower() == "csv":
            # Try to find CSV file in multiple locations
            csv_found = False
            df = None
            
            # Try R2 location first
            if settings.should_use_cloud_storage:
                r2_csv_path = f"csv/{file_metadata.filename}"
                if storage.file_exists(r2_csv_path):
                    csv_content = await storage.read_file(r2_csv_path)
                    temp_path = f"temp_read_{file_metadata.filename}"
                    async with aiofiles.open(temp_path, 'wb') as f:
                        await f.write(csv_content)
                    df = read_csv_robust(temp_path)
                    os.remove(temp_path)
                    csv_found = True
            
            # Try local location if not found in R2
            if not csv_found:
                local_csv_path = f"uploads/{file_metadata.filename}"
                if os.path.exists(local_csv_path):
                    df = read_csv_robust(local_csv_path)
                    csv_found = True
            
            if not csv_found:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"CSV file '{file_metadata.filename}' not found in any storage location"
                )
                
        else:
            # Try to find Parquet file in multiple locations
            parquet_found = False
            df = None
            
            if not file_metadata.parquet_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No parquet file path recorded for this file"
                )
            
            # Try R2 location first (if parquet_path looks like R2 path)
            if settings.should_use_cloud_storage and file_metadata.parquet_path.startswith("parquet/"):
                r2_parquet_path = file_metadata.parquet_path
                if storage.file_exists(r2_parquet_path):
                    parquet_content = await storage.read_file(r2_parquet_path)
                    temp_path = f"temp_read_{file_metadata.filename.replace('.csv', '.parquet')}"
                    async with aiofiles.open(temp_path, 'wb') as f:
                        await f.write(parquet_content)
                    df = pd.read_parquet(temp_path)
                    os.remove(temp_path)
                    parquet_found = True
            
            # Try local location if not found in R2
            if not parquet_found and os.path.exists(file_metadata.parquet_path):
                df = pd.read_parquet(file_metadata.parquet_path)
                parquet_found = True
            
            if not parquet_found:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parquet file not found at '{file_metadata.parquet_path}' in any storage location"
                )
        
        # Apply pagination
        total_rows = len(df)
        paginated_df = df.iloc[offset:offset + limit]
        
        # Convert to JSON-serializable format with robust handling
        data = df_to_json_safe(paginated_df)
        
        return {
            "file_id": file_id,
            "filename": file_metadata.filename,
            "format": format,
            "total_rows": total_rows,
            "returned_rows": len(data),
            "offset": offset,
            "limit": limit,
            "columns": df.columns.tolist(),
            "data": data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading file data: {str(e)}"
        )

@router.get("/files/{file_id}/statistics")
async def get_file_statistics(
    file_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed statistics about a processed file
    
    Returns comprehensive data analysis including:
    - Column information and data types
    - Missing values analysis
    - File size comparison
    - Data quality metrics
    """
    file_metadata = db_manager.get_metadata_by_id(file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if file_metadata.status != "Done":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is not ready. Status: {file_metadata.status}"
        )
    
    try:
        # Find parquet file in multiple locations
        parquet_df = None
        parquet_size_bytes = 0
        
        if file_metadata.parquet_path:
            # Try R2 location first
            if settings.should_use_cloud_storage and file_metadata.parquet_path.startswith("parquet/"):
                if storage.file_exists(file_metadata.parquet_path):
                    try:
                        parquet_content = await storage.read_file(file_metadata.parquet_path)
                        temp_path = f"temp_stats_{file_metadata.filename.replace('.csv', '.parquet')}"
                        async with aiofiles.open(temp_path, 'wb') as f:
                            await f.write(parquet_content)
                        parquet_df = pd.read_parquet(temp_path)
                        parquet_size_bytes = len(parquet_content)
                        os.remove(temp_path)
                    except Exception:
                        pass
            
            # Try local location if not found in R2
            if parquet_df is None and os.path.exists(file_metadata.parquet_path):
                parquet_df = pd.read_parquet(file_metadata.parquet_path)
                parquet_size_bytes = os.path.getsize(file_metadata.parquet_path)
        
        if parquet_df is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parquet file not found for '{file_metadata.filename}'"
            )
        
        # Find CSV file for size comparison
        csv_size_bytes = 0
        if settings.should_use_cloud_storage:
            csv_r2_path = f"csv/{file_metadata.filename}"
            if storage.file_exists(csv_r2_path):
                csv_size_bytes = storage.get_file_size(csv_r2_path)
        
        # Try local CSV if not found in R2
        if csv_size_bytes == 0:
            local_csv_path = f"uploads/{file_metadata.filename}"
            if os.path.exists(local_csv_path):
                csv_size_bytes = os.path.getsize(local_csv_path)
        
        # Calculate statistics
        stats = {
            "file_info": {
                "id": file_id,
                "filename": file_metadata.filename,
                "upload_timestamp": file_metadata.upload_timestamp.isoformat(),
                "status": file_metadata.status,
                "total_rows": len(parquet_df),
                "total_columns": len(parquet_df.columns)
            },
            "columns": [],
            "data_quality": {
                "total_missing_values": int(parquet_df.isnull().sum().sum()),
                "missing_percentage": sanitize_for_json((parquet_df.isnull().sum().sum() / (len(parquet_df) * len(parquet_df.columns))) * 100),
                "duplicate_rows": int(parquet_df.duplicated().sum()),
                "unique_rows": len(parquet_df.drop_duplicates())
            },
            "file_sizes": {
                "csv_size_bytes": csv_size_bytes,
                "parquet_size_bytes": parquet_size_bytes
            }
        }
        
        # Calculate compression ratio
        if stats["file_sizes"]["csv_size_bytes"] > 0:
            stats["file_sizes"]["compression_ratio"] = round(
                stats["file_sizes"]["csv_size_bytes"] / stats["file_sizes"]["parquet_size_bytes"], 2
            )
            stats["file_sizes"]["space_saved_percentage"] = round(
                ((stats["file_sizes"]["csv_size_bytes"] - stats["file_sizes"]["parquet_size_bytes"]) / 
                 stats["file_sizes"]["csv_size_bytes"]) * 100, 2
            )
        
        # Column-level statistics
        for column in parquet_df.columns:
            missing_count = int(parquet_df[column].isnull().sum())
            missing_percentage = sanitize_for_json((missing_count / len(parquet_df)) * 100) if len(parquet_df) > 0 else 0.0
            
            # Get sample values and handle different data types
            sample_values = []
            try:
                # Get non-null sample values and convert to JSON-serializable types
                samples = parquet_df[column].dropna().head(5)
                sample_values = [sanitize_for_json(val) for val in samples]
            except Exception:
                sample_values = ["N/A"]
            
            col_stats = {
                "name": column,
                "data_type": str(parquet_df[column].dtype),
                "missing_count": missing_count,
                "missing_percentage": round(missing_percentage, 2),
                "unique_count": int(parquet_df[column].nunique()),
                "sample_values": sample_values
            }
            
            # Add numeric statistics if column is numeric
            if parquet_df[column].dtype in ['int64', 'float64', 'int32', 'float32']:
                try:
                    numeric_col = pd.to_numeric(parquet_df[column], errors='coerce')
                    if not numeric_col.isnull().all():
                        min_val = numeric_col.min()
                        max_val = numeric_col.max()
                        mean_val = numeric_col.mean()
                        median_val = numeric_col.median()
                        
                        col_stats.update({
                            "min_value": sanitize_for_json(min_val),
                            "max_value": sanitize_for_json(max_val),
                            "mean_value": sanitize_for_json(round(float(mean_val), 2) if pd.isfinite(mean_val) else None),
                            "median_value": sanitize_for_json(median_val)
                        })
                except Exception:
                    # If numeric conversion fails, skip numeric stats
                    pass
            
            stats["columns"].append(col_stats)
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating statistics: {str(e)}"
        )

@router.get("/files/{file_id}/preview")
async def get_file_preview(
    file_id: int,
    rows: Optional[int] = Query(10, description="Number of rows to preview"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a quick preview of the file data
    
    Returns first N rows of both CSV and Parquet formats for comparison
    """
    file_metadata = db_manager.get_metadata_by_id(file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    try:
        preview_data = {
            "file_id": file_id,
            "filename": file_metadata.filename,
            "status": file_metadata.status,
            "rows_requested": rows
        }
        
        # CSV preview - try multiple locations
        csv_found = False
        
        # Try R2 location first
        if settings.should_use_cloud_storage:
            csv_r2_path = f"csv/{file_metadata.filename}"
            if storage.file_exists(csv_r2_path):
                try:
                    csv_content = await storage.read_file(csv_r2_path)
                    temp_path = f"temp_preview_csv_{file_metadata.filename}"
                    async with aiofiles.open(temp_path, 'wb') as f:
                        await f.write(csv_content)
                    csv_df = read_csv_robust(temp_path).head(rows)
                    preview_data["csv_preview"] = {
                        "columns": csv_df.columns.tolist(),
                        "data": df_to_json_safe(csv_df),
                        "rows_returned": len(csv_df)
                    }
                    os.remove(temp_path)
                    csv_found = True
                except Exception:
                    pass
        
        # Try local location if not found in R2
        if not csv_found:
            local_csv_path = f"uploads/{file_metadata.filename}"
            if os.path.exists(local_csv_path):
                csv_df = read_csv_robust(local_csv_path).head(rows)
                preview_data["csv_preview"] = {
                    "columns": csv_df.columns.tolist(),
                    "data": df_to_json_safe(csv_df),
                    "rows_returned": len(csv_df)
                }
                csv_found = True
        
        # Parquet preview - try multiple locations
        if file_metadata.status == "Done" and file_metadata.parquet_path:
            parquet_found = False
            
            # Try R2 location first
            if settings.should_use_cloud_storage and file_metadata.parquet_path.startswith("parquet/"):
                if storage.file_exists(file_metadata.parquet_path):
                    try:
                        parquet_content = await storage.read_file(file_metadata.parquet_path)
                        temp_path = f"temp_preview_parquet_{file_metadata.filename.replace('.csv', '.parquet')}"
                        async with aiofiles.open(temp_path, 'wb') as f:
                            await f.write(parquet_content)
                        parquet_df = pd.read_parquet(temp_path).head(rows)
                        preview_data["parquet_preview"] = {
                            "columns": parquet_df.columns.tolist(),
                            "data": df_to_json_safe(parquet_df),
                            "rows_returned": len(parquet_df)
                        }
                        os.remove(temp_path)
                        parquet_found = True
                    except Exception:
                        pass
            
            # Try local location if not found in R2
            if not parquet_found and os.path.exists(file_metadata.parquet_path):
                parquet_df = pd.read_parquet(file_metadata.parquet_path).head(rows)
                preview_data["parquet_preview"] = {
                    "columns": parquet_df.columns.tolist(),
                    "data": df_to_json_safe(parquet_df),
                    "rows_returned": len(parquet_df)
                }
                parquet_found = True
        
        return preview_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating preview: {str(e)}"
        )

@router.get("/files/{file_id}/download")
async def get_download_url(
    file_id: int,
    format: Optional[str] = Query("parquet", description="File format to download: 'csv' or 'parquet'"),
    expiration_hours: Optional[int] = Query(1, description="URL expiration time in hours (1-24)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a secure download URL for a processed file
    
    - Returns presigned URLs for cloud storage (R2)
    - Returns direct download endpoint for local storage
    - Supports both CSV and Parquet formats
    - Configurable expiration time (1-24 hours)
    """
    file_metadata = db_manager.get_metadata_by_id(file_id)
    if not file_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Validate expiration time
    if expiration_hours < 1 or expiration_hours > 24:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expiration time must be between 1 and 24 hours"
        )
    
    expiration_seconds = expiration_hours * 3600
    
    try:
        if format.lower() == "csv":
            # Download original CSV file
            if settings.should_use_cloud_storage:
                file_path = f"csv/{file_metadata.filename}"
                if not storage.file_exists(file_path):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Original CSV file not found in cloud storage"
                    )
            else:
                file_path = f"uploads/{file_metadata.filename}"
                if not os.path.exists(file_path):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Original CSV file not found in local storage"
                    )
            
            download_url = storage.generate_download_url(file_path, expiration_seconds)
            file_size = storage.get_file_size(file_path)
            
        else:  # parquet format
            if file_metadata.status != "Done":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File is not ready for download. Status: {file_metadata.status}"
                )
            
            if not file_metadata.parquet_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parquet file not found"
                )
            
            # Check if file exists in storage
            parquet_found = False
            
            # Try R2 location first
            if settings.should_use_cloud_storage and file_metadata.parquet_path.startswith("parquet/"):
                if storage.file_exists(file_metadata.parquet_path):
                    parquet_found = True
            
            # Try local location if not found in R2
            if not parquet_found and os.path.exists(file_metadata.parquet_path):
                parquet_found = True
            
            if not parquet_found:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parquet file not found in any storage location"
                )
            
            download_url = storage.generate_download_url(file_metadata.parquet_path, expiration_seconds)
            file_size = storage.get_file_size(file_metadata.parquet_path)
        
        return {
            "download_url": download_url,
            "file_info": {
                "id": file_id,
                "filename": file_metadata.filename,
                "format": format.lower(),
                "size_bytes": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2) if file_size > 0 else 0,
                "rows": file_metadata.row_count
            },
            "url_info": {
                "expires_in_hours": expiration_hours,
                "expires_in_seconds": expiration_seconds,
                "storage_type": "cloud" if settings.should_use_cloud_storage else "local",
                "generated_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating download URL: {str(e)}"
        )

@router.get("/files/download/local/{file_path:path}")
async def download_local_file(
    file_path: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Direct download endpoint for local files
    
    This endpoint is used when storage is local (development mode)
    The file_path should be relative to the project root
    """
    # Security check - ensure file_path is within allowed directories
    allowed_prefixes = ["uploads/", "parquet/"]
    if not any(file_path.startswith(prefix) for prefix in allowed_prefixes):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this file path is not allowed"
        )
    
    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Determine filename and media type
    filename = os.path.basename(file_path)
    
    if file_path.endswith('.csv'):
        media_type = 'text/csv'
    elif file_path.endswith('.parquet'):
        media_type = 'application/octet-stream'
    else:
        media_type = 'application/octet-stream'
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache"
        }
    )

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