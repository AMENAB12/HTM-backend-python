from fastapi import APIRouter, Depends
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path

from ..dependencies import get_current_user
from ...core.database import DatabaseManager

router = APIRouter(tags=["Dashboard"])

# Initialize database manager
db_manager = DatabaseManager()

@router.get("/dashboard/overview")
async def get_dashboard_overview(current_user: dict = Depends(get_current_user)):
    """
    Get comprehensive dashboard overview with all key metrics
    
    Returns:
    - File processing statistics
    - Storage analytics 
    - Data quality metrics
    - Recent activity
    - Performance insights
    """
    try:
        # Get all files from database
        all_files = db_manager.get_all_metadata()
        
        # Basic file statistics
        total_files = len(all_files)
        processed_files = len([f for f in all_files if f.status == "Done"])
        processing_files = len([f for f in all_files if f.status == "Processing"])
        error_files = len([f for f in all_files if f.status == "Error"])
        
        # Data volume statistics
        total_rows_processed = sum(f.row_count for f in all_files if f.status == "Done")
        total_rows_all = sum(f.row_count for f in all_files)
        
        # Storage calculations
        uploads_dir = Path("uploads")
        parquet_dir = Path("parquet")
        
        total_csv_size = sum(
            os.path.getsize(uploads_dir / f.filename) 
            for f in all_files 
            if (uploads_dir / f.filename).exists()
        )
        
        total_parquet_size = sum(
            os.path.getsize(f.parquet_path) 
            for f in all_files 
            if f.parquet_path and os.path.exists(f.parquet_path)
        )
        
        compression_ratio = total_csv_size / total_parquet_size if total_parquet_size > 0 else 0
        space_saved = total_csv_size - total_parquet_size
        space_saved_percentage = (space_saved / total_csv_size * 100) if total_csv_size > 0 else 0
        
        # Recent activity (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        recent_files = [f for f in all_files if f.upload_timestamp >= week_ago]
        
        # File size distribution
        file_sizes = []
        for f in all_files:
            if f.status == "Done":
                csv_path = uploads_dir / f.filename
                if csv_path.exists():
                    size_mb = os.path.getsize(csv_path) / (1024 * 1024)
                    file_sizes.append({
                        "filename": f.filename,
                        "size_mb": round(size_mb, 2),
                        "rows": f.row_count,
                        "upload_date": f.upload_timestamp.isoformat()
                    })
        
        # Processing success rate
        success_rate = (processed_files / total_files * 100) if total_files > 0 else 0
        
        # Average processing metrics
        avg_rows_per_file = total_rows_processed / processed_files if processed_files > 0 else 0
        avg_compression = compression_ratio
        
        dashboard_data = {
            # Overview metrics
            "overview": {
                "total_files": total_files,
                "processed_files": processed_files,
                "processing_files": processing_files,
                "error_files": error_files,
                "success_rate_percentage": round(success_rate, 1),
                "total_rows_processed": total_rows_processed,
                "average_rows_per_file": round(avg_rows_per_file, 0)
            },
            
            # Storage analytics
            "storage": {
                "total_csv_size_bytes": total_csv_size,
                "total_parquet_size_bytes": total_parquet_size,
                "space_saved_bytes": space_saved,
                "space_saved_percentage": round(space_saved_percentage, 1),
                "compression_ratio": round(compression_ratio, 2),
                "total_csv_size_mb": round(total_csv_size / (1024 * 1024), 2),
                "total_parquet_size_mb": round(total_parquet_size / (1024 * 1024), 2)
            },
            
            # Recent activity
            "recent_activity": {
                "files_this_week": len(recent_files),
                "rows_this_week": sum(f.row_count for f in recent_files),
                "latest_uploads": [
                    {
                        "filename": f.filename,
                        "upload_time": f.upload_timestamp.isoformat(),
                        "status": f.status,
                        "rows": f.row_count
                    }
                    for f in sorted(all_files, key=lambda x: x.upload_timestamp, reverse=True)[:5]
                ]
            },
            
            # File distribution
            "file_distribution": {
                "by_status": {
                    "done": processed_files,
                    "processing": processing_files,
                    "error": error_files
                },
                "largest_files": sorted(file_sizes, key=lambda x: x["size_mb"], reverse=True)[:5],
                "most_rows": sorted(file_sizes, key=lambda x: x["rows"], reverse=True)[:5]
            },
            
            # Performance metrics
            "performance": {
                "average_compression_ratio": round(avg_compression, 2),
                "total_storage_saved_mb": round(space_saved / (1024 * 1024), 2),
                "processing_efficiency": round(success_rate, 1)
            }
        }
        
        return dashboard_data
        
    except Exception as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating dashboard data: {str(e)}"
        )

@router.get("/dashboard/activity")
async def get_activity_timeline(
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """
    Get activity timeline for the specified number of days

    Returns daily activity metrics for charting, with the most recent date on top (descending order)
    """
    try:
        all_files = db_manager.get_all_metadata()

        # Generate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days-1)

        activity_data = []
        # Collect dates in descending order (most recent first)
        date_list = [end_date - timedelta(days=i) for i in range(days)]
        for current_date in date_list:
            # Filter files for this date
            date_files = [
                f for f in all_files 
                if f.upload_timestamp.date() == current_date
            ]

            daily_stats = {
                "date": current_date.isoformat(),
                "files_uploaded": len(date_files),
                "files_processed": len([f for f in date_files if f.status == "Done"]),
                "files_failed": len([f for f in date_files if f.status == "Error"]),
                "total_rows": sum(f.row_count for f in date_files),
                "total_size_mb": 0
            }

            # Calculate total size for the day
            total_size = 0
            for f in date_files:
                csv_path = Path("uploads") / f.filename
                if csv_path.exists():
                    total_size += os.path.getsize(csv_path)
            daily_stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)

            activity_data.append(daily_stats)

        # activity_data is already in descending order (recent date first)
        return {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily_activity": activity_data,
            "summary": {
                "total_files": sum(day["files_uploaded"] for day in activity_data),
                "total_processed": sum(day["files_processed"] for day in activity_data),
                "total_rows": sum(day["total_rows"] for day in activity_data),
                "total_size_mb": sum(day["total_size_mb"] for day in activity_data)
            }
        }

    except Exception as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating activity timeline: {str(e)}"
        )

@router.get("/dashboard/data-quality")
async def get_data_quality_overview(current_user: dict = Depends(get_current_user)):
    """
    Get data quality overview across all processed files
    
    Returns aggregated data quality metrics
    """
    try:
        all_files = db_manager.get_all_metadata()
        processed_files = [f for f in all_files if f.status == "Done"]
        
        if not processed_files:
            return {
                "message": "No processed files found",
                "total_processed_files": 0
            }
        
        quality_metrics = {
            "total_files_analyzed": len(processed_files),
            "column_analysis": {},
            "data_completeness": [],
            "file_quality_scores": []
        }
        
        # Analyze each processed file
        for file_meta in processed_files[:10]:  # Limit to 10 files for performance
            if not file_meta.parquet_path or not os.path.exists(file_meta.parquet_path):
                continue
                
            try:
                df = pd.read_parquet(file_meta.parquet_path)
                
                # Calculate completeness
                total_cells = len(df) * len(df.columns)
                missing_cells = df.isnull().sum().sum()
                completeness = ((total_cells - missing_cells) / total_cells * 100) if total_cells > 0 else 0
                
                # Calculate quality score
                duplicate_ratio = (df.duplicated().sum() / len(df) * 100) if len(df) > 0 else 0
                quality_score = completeness - (duplicate_ratio * 0.5)  # Penalize duplicates
                
                quality_metrics["data_completeness"].append({
                    "filename": file_meta.filename,
                    "completeness_percentage": round(completeness, 2),
                    "missing_values": int(missing_cells),
                    "total_cells": int(total_cells),
                    "duplicate_rows": int(df.duplicated().sum())
                })
                
                quality_metrics["file_quality_scores"].append({
                    "filename": file_meta.filename,
                    "quality_score": round(quality_score, 2),
                    "rows": len(df),
                    "columns": len(df.columns)
                })
                
            except Exception as e:
                continue  # Skip files that can't be read
        
        # Calculate overall metrics
        if quality_metrics["data_completeness"]:
            avg_completeness = sum(
                item["completeness_percentage"] 
                for item in quality_metrics["data_completeness"]
            ) / len(quality_metrics["data_completeness"])
            
            avg_quality_score = sum(
                item["quality_score"] 
                for item in quality_metrics["file_quality_scores"]
            ) / len(quality_metrics["file_quality_scores"])
            
            quality_metrics["overall"] = {
                "average_completeness": round(avg_completeness, 2),
                "average_quality_score": round(avg_quality_score, 2),
                "files_with_high_quality": len([
                    f for f in quality_metrics["file_quality_scores"] 
                    if f["quality_score"] >= 90
                ]),
                "files_with_issues": len([
                    f for f in quality_metrics["data_completeness"] 
                    if f["completeness_percentage"] < 95
                ])
            }
        
        return quality_metrics
        
    except Exception as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating data quality overview: {str(e)}"
        )

@router.get("/dashboard/system-stats")
async def get_system_statistics(current_user: dict = Depends(get_current_user)):
    """
    Get system-level statistics and health metrics
    """
    try:
        # Directory statistics
        uploads_dir = Path("uploads")
        parquet_dir = Path("parquet")
        
        def get_directory_stats(directory: Path):
            if not directory.exists():
                return {"exists": False, "file_count": 0, "total_size_bytes": 0}
            
            files = list(directory.glob("*"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            
            return {
                "exists": True,
                "file_count": len([f for f in files if f.is_file()]),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
        
        # Database statistics
        db_stats = db_manager.get_statistics()
        
        # System info
        system_stats = {
            "directories": {
                "uploads": get_directory_stats(uploads_dir),
                "parquet": get_directory_stats(parquet_dir)
            },
            "database": db_stats,
            "processing": {
                "supported_formats": ["CSV", "TSV", "TXT"],
                "supported_encodings": ["UTF-8", "Latin1", "CP1252", "ISO-8859-1"],
                "supported_delimiters": ["Comma", "Semicolon", "Tab", "Pipe", "Auto-detect"],
                "max_file_size_mb": 100,
                "processing_timeout_seconds": 30
            },
            "api_info": {
                "version": "1.0.0",
                "uptime_check": datetime.now().isoformat(),
                "token_expiry_days": 7,
                "cors_enabled": True
            }
        }
        
        return system_stats
        
    except Exception as e:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating system statistics: {str(e)}"
        ) 