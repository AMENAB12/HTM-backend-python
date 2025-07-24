from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Query
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
        
        # Read CSV and validate (with robust error handling)
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
            # Return original CSV data
            csv_path = f"uploads/{file_metadata.filename}"
            if not os.path.exists(csv_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Original CSV file not found"
                )
            # Read CSV with robust error handling
            df = read_csv_robust(csv_path)
        else:
            # Return Parquet data
            if not file_metadata.parquet_path or not os.path.exists(file_metadata.parquet_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parquet file not found"
                )
            df = pd.read_parquet(file_metadata.parquet_path)
        
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
        csv_path = f"uploads/{file_metadata.filename}"
        parquet_path = file_metadata.parquet_path
        
        # Read both files for comparison
        csv_df = read_csv_robust(csv_path) if os.path.exists(csv_path) else None
        parquet_df = pd.read_parquet(parquet_path) if os.path.exists(parquet_path) else None
        
        if parquet_df is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Processed file not found"
            )
        
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
                "csv_size_bytes": os.path.getsize(csv_path) if csv_path and os.path.exists(csv_path) else 0,
                "parquet_size_bytes": os.path.getsize(parquet_path) if os.path.exists(parquet_path) else 0
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
        csv_path = f"uploads/{file_metadata.filename}"
        parquet_path = file_metadata.parquet_path
        
        preview_data = {
            "file_id": file_id,
            "filename": file_metadata.filename,
            "status": file_metadata.status,
            "rows_requested": rows
        }
        
        # CSV preview
        if os.path.exists(csv_path):
            csv_df = read_csv_robust(csv_path).head(rows)
            # Use robust JSON serialization
            preview_data["csv_preview"] = {
                "columns": csv_df.columns.tolist(),
                "data": df_to_json_safe(csv_df),
                "rows_returned": len(csv_df)
            }
        
        # Parquet preview (if processed)
        if file_metadata.status == "Done" and parquet_path and os.path.exists(parquet_path):
            parquet_df = pd.read_parquet(parquet_path).head(rows)
            # Use robust JSON serialization
            preview_data["parquet_preview"] = {
                "columns": parquet_df.columns.tolist(),
                "data": df_to_json_safe(parquet_df),
                "rows_returned": len(parquet_df)
            }
        
        return preview_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating preview: {str(e)}"
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