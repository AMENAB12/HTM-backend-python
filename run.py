#!/usr/bin/env python3
"""
Startup script for the CSV to Parquet Converter API
"""

import os
import sys
import argparse
import uvicorn
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings

def main():
    """Main entry point for the application"""
    parser = argparse.ArgumentParser(description="CSV to Parquet Converter API")
    
    parser.add_argument(
        "--host", 
        default="0.0.0.0", 
        help="Host to bind the server to"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port to bind the server to"
    )
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug mode"
    )
    parser.add_argument(
        "--env", 
        choices=["development", "production"], 
        default="development",
        help="Environment mode"
    )
    
    args = parser.parse_args()
    
    # Set environment variables
    os.environ["ENVIRONMENT"] = args.env
    if args.debug:
        os.environ["DEBUG"] = "true"
    
    # Get settings
    settings = get_settings()
    
    # Configure uvicorn
    uvicorn_config = {
        "app": "app.main:app",
        "host": args.host,
        "port": args.port,
        "reload": args.reload or args.env == "development",
        "log_level": "debug" if args.debug else "info",
        "access_log": True,
    }
    
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Environment: {args.env}")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"API Docs: http://{args.host}:{args.port}/docs")
    print(f"Debug mode: {args.debug}")
    print(f"Auto-reload: {uvicorn_config['reload']}")
    
    # Start the server
    uvicorn.run(**uvicorn_config)

if __name__ == "__main__":
    main() 