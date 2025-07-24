from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "CSV to Parquet Converter API"
    }

@router.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "CSV to Parquet Converter API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    } 