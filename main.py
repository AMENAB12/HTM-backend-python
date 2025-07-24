from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import pandas as pd
import sqlite3
from datetime import datetime
import asyncio
from typing import List, Optional
import aiofiles
from pathlib import Path

# Import our modules
from database import DatabaseManager, FileMetadata
from auth import AuthManager

app = FastAPI(
    title="CSV to Parquet Converter API", 
    version="1.0.0",
    description="A FastAPI backend for uploading CSV files and converting them to Parquet format"
)

# Initialize managers
db_manager = DatabaseManager()
auth_manager = AuthManager()
security = HTTPBearer()

# Import configuration
from config import get_settings

# Get settings instance
config_settings = get_settings()

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=config_settings.get_cors_origins_list(),  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("parquet", exist_ok=True)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate JWT token and return user info"""
    token = credentials.credentials
    if not auth_manager.verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": "test"}  # For simplicity, return fixed user

@app.post("/login", tags=["Authentication"])
async def login(credentials: dict):
    """
    Login endpoint that accepts username and password
    
    Expected payload:
    {
        "username": "test",
        "password": "password"
    }
    """
    username = credentials.get("username")
    password = credentials.get("password")
    
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required"
        )
    
    if username == "test" and password == "password":
        token = auth_manager.create_access_token({"sub": username})
        return {
            "access_token": token, 
            "token_type": "bearer",
            "message": "Login successful"
        }
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password"
    )

@app.post("/upload", tags=["File Operations"])
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
            status = "Error"
            parquet_path = None
        else:
            status = "Processing"
            # Convert to Parquet
            parquet_filename = file.filename.replace('.csv', '.parquet')
            parquet_path = f"parquet/{parquet_filename}"
            df.to_parquet(parquet_path, index=False)
            
    except pd.errors.EmptyDataError:
        status = "Error"
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
        status=status
    )
    
    file_id = db_manager.insert_metadata(metadata)
    
    # Prepare response data
    response_data = {
        "id": file_id,
        "filename": file.filename,
        "upload_timestamp": metadata.upload_timestamp.isoformat(),
        "row_count": row_count,
        "status": status,
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

@app.get("/files", tags=["File Operations"])
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

@app.get("/files/{file_id}", tags=["File Operations"])
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

@app.delete("/files/{file_id}", tags=["File Operations"])
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

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "CSV to Parquet Converter API"
    }

@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "CSV to Parquet Converter API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 