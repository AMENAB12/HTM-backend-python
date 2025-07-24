"""
Cloud Storage Service for R2/S3 compatibility
"""

import aiofiles
import os
from typing import Optional, BinaryIO
from pathlib import Path
import asyncio

# Optional cloud storage imports
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    boto3 = None
    ClientError = Exception

from .config import get_settings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StorageService:
    """
    Unified storage service that works with both local and cloud storage
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._s3_client = None
        self._debug_mode = True  # Enable detailed logging
        self._log_r2_config()
    
    def _log_r2_config(self):
        """Log R2 configuration for debugging"""
        if self._debug_mode:
            logger.info("=== R2 STORAGE CONFIGURATION ===")
            logger.info(f"USE_CLOUD_STORAGE: {self.settings.use_cloud_storage}")
            logger.info(f"R2_ENDPOINT_URL: {self.settings.r2_endpoint_url}")
            logger.info(f"R2_BUCKET_NAME: {self.settings.r2_bucket_name}")
            logger.info(f"R2_REGION: {self.settings.r2_region}")
            logger.info(f"R2_ACCESS_KEY_ID: {'SET' if self.settings.r2_access_key_id else 'NOT SET'}")
            logger.info(f"R2_SECRET_ACCESS_KEY: {'SET' if self.settings.r2_secret_access_key else 'NOT SET'}")
            logger.info(f"BOTO3_AVAILABLE: {HAS_BOTO3}")
            logger.info(f"SHOULD_USE_CLOUD: {self.settings.should_use_cloud_storage}")
            logger.info("================================")
    
    @property
    def s3_client(self):
        """Lazy initialization of S3 client with error handling"""
        if self._s3_client is None and self.settings.should_use_cloud_storage and HAS_BOTO3:
            try:
                if self._debug_mode:
                    logger.info("🔧 Initializing R2/S3 client...")
                
                self._s3_client = boto3.client(
                    's3',
                    endpoint_url=self.settings.r2_endpoint_url,
                    aws_access_key_id=self.settings.r2_access_key_id,
                    aws_secret_access_key=self.settings.r2_secret_access_key,
                    region_name=self.settings.r2_region
                )
                
                if self._debug_mode:
                    logger.info("✅ R2/S3 client initialized successfully")
                    
            except Exception as e:
                logger.error(f"❌ Failed to initialize R2/S3 client: {str(e)}")
                logger.error(f"📝 Check your R2 credentials and endpoint URL")
                self._s3_client = None
                
        return self._s3_client
    
    async def save_file(self, file_content: bytes, filename: str, file_type: str = "csv") -> str:
        """
        Save file to storage (local or cloud)
        
        Args:
            file_content: File content as bytes
            filename: Name of the file
            file_type: Type of file (csv, parquet)
            
        Returns:
            File path or URL
        """
        if self._debug_mode:
            logger.info(f"💾 Saving file: {filename} ({file_type}) - {len(file_content)} bytes")
        
        # Check if we should use cloud storage
        use_cloud = self.settings.should_use_cloud_storage and HAS_BOTO3
        
        if self._debug_mode:
            logger.info(f"🌐 Storage decision: {'CLOUD' if use_cloud else 'LOCAL'}")
        
        if use_cloud:
            try:
                return await self._save_to_cloud(file_content, filename, file_type)
            except Exception as e:
                logger.error(f"❌ Cloud storage failed: {str(e)}")
                logger.info("🔄 Falling back to local storage...")
                return await self._save_to_local(file_content, filename, file_type)
        else:
            # Use local storage
            return await self._save_to_local(file_content, filename, file_type)
    
    async def read_file(self, file_path: str) -> bytes:
        """
        Read file from storage (local or cloud)
        
        Args:
            file_path: Path to the file or S3 key
            
        Returns:
            File content as bytes
        """
        if self.settings.should_use_cloud_storage and HAS_BOTO3:
            return await self._read_from_cloud(file_path)
        else:
            return await self._read_from_local(file_path)
    
    async def delete_file(self, file_path: str) -> bool:
        """
        Delete file from storage (local or cloud)
        
        Args:
            file_path: Path to the file or S3 key
            
        Returns:
            True if successful, False otherwise
        """
        if self.settings.should_use_cloud_storage and HAS_BOTO3:
            return await self._delete_from_cloud(file_path)
        else:
            return await self._delete_from_local(file_path)
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if file exists in storage (local or cloud)
        
        Args:
            file_path: Path to the file or S3 key
            
        Returns:
            True if file exists, False otherwise
        """
        if self.settings.should_use_cloud_storage and HAS_BOTO3:
            return self._cloud_file_exists(file_path)
        else:
            return os.path.exists(file_path)
    
    def get_file_size(self, file_path: str) -> int:
        """
        Get file size from storage (local or cloud)
        
        Args:
            file_path: Path to the file or S3 key
            
        Returns:
            File size in bytes
        """
        if self.settings.should_use_cloud_storage and HAS_BOTO3:
            return self._get_cloud_file_size(file_path)
        else:
            return os.path.getsize(file_path) if os.path.exists(file_path) else 0
    
    def generate_download_url(self, file_path: str, expiration: int = 3600) -> str:
        """
        Generate a download URL for a file (presigned URL for cloud, direct path for local)
        
        Args:
            file_path: Path to the file or S3 key
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Download URL
        """
        if self.settings.should_use_cloud_storage and HAS_BOTO3:
            return self._generate_presigned_url(file_path, expiration)
        else:
            # For local storage, return the file path (will be served by FastAPI)
            return f"/files/download/local/{file_path}"
    
    # Local storage methods
    async def _save_to_local(self, file_content: bytes, filename: str, file_type: str) -> str:
        """Save file to local storage"""
        if file_type == "csv":
            directory = self.settings.upload_dir
        else:
            directory = self.settings.parquet_dir
        
        # Ensure directory exists
        os.makedirs(directory, exist_ok=True)
        
        file_path = os.path.join(directory, filename)
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        return file_path
    
    async def _read_from_local(self, file_path: str) -> bytes:
        """Read file from local storage"""
        async with aiofiles.open(file_path, 'rb') as f:
            return await f.read()
    
    async def _delete_from_local(self, file_path: str) -> bool:
        """Delete file from local storage"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception:
            return False
    
    # Cloud storage methods
    async def _save_to_cloud(self, file_content: bytes, filename: str, file_type: str) -> str:
        """Save file to R2/S3 with detailed error handling"""
        key = f"{file_type}/{filename}"
        
        if self._debug_mode:
            logger.info(f"☁️ Uploading to R2: {key}")
        
        # Check if S3 client is available
        if not self.s3_client:
            raise Exception("R2/S3 client not initialized - check credentials and configuration")
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            
            if self._debug_mode:
                logger.info(f"📤 Starting upload to bucket: {self.settings.r2_bucket_name}")
            
            result = await loop.run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.settings.r2_bucket_name,
                    Key=key,
                    Body=file_content,
                    ContentType='text/csv' if file_type == 'csv' else 'application/octet-stream'
                )
            )
            
            if self._debug_mode:
                logger.info(f"✅ Successfully uploaded to R2: {key}")
                logger.info(f"📊 Upload result: {result.get('ETag', 'No ETag')}")
            
            return key
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"❌ R2 ClientError ({error_code}): {error_message}")
            
            if error_code == 'NoSuchBucket':
                raise Exception(f"R2 bucket '{self.settings.r2_bucket_name}' does not exist - create it in Cloudflare dashboard")
            elif error_code == 'AccessDenied':
                raise Exception("R2 access denied - check your API token permissions")
            elif error_code == 'InvalidAccessKeyId':
                raise Exception("Invalid R2 access key - check your R2_ACCESS_KEY_ID")
            else:
                raise Exception(f"R2 upload failed ({error_code}): {error_message}")
                
        except Exception as e:
            logger.error(f"❌ Unexpected error uploading to R2: {str(e)}")
            raise Exception(f"R2 upload failed: {str(e)}")
    
    async def _read_from_cloud(self, key: str) -> bytes:
        """Read file from R2/S3"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.s3_client.get_object(
                    Bucket=self.settings.r2_bucket_name,
                    Key=key
                )
            )
            return response['Body'].read()
        except Exception as e:
            raise Exception(f"Failed to read from cloud storage: {str(e)}")
    
    async def _delete_from_cloud(self, key: str) -> bool:
        """Delete file from R2/S3"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.delete_object(
                    Bucket=self.settings.r2_bucket_name,
                    Key=key
                )
            )
            return True
        except Exception:
            return False
    
    def _cloud_file_exists(self, key: str) -> bool:
        """Check if file exists in R2/S3"""
        try:
            self.s3_client.head_object(
                Bucket=self.settings.r2_bucket_name,
                Key=key
            )
            return True
        except ClientError:
            return False
    
    def _get_cloud_file_size(self, key: str) -> int:
        """Get file size from R2/S3"""
        try:
            response = self.s3_client.head_object(
                Bucket=self.settings.r2_bucket_name,
                Key=key
            )
            return response['ContentLength']
        except ClientError:
            return 0
    
    def _generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for downloading from R2/S3"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.settings.r2_bucket_name,
                    'Key': key
                },
                ExpiresIn=expiration
            )
            if self._debug_mode:
                logger.info(f"📤 Generated download URL for: {key} (expires in {expiration}s)")
            return url
        except Exception as e:
            logger.error(f"❌ Failed to generate presigned URL for {key}: {str(e)}")
            # Fallback to direct S3 URL (may not work without auth)
            return f"{self.settings.r2_endpoint_url}/{self.settings.r2_bucket_name}/{key}"
    
    def get_file_url(self, file_path: str) -> str:
        """
        Get a URL for accessing the file
        
        For cloud storage, this could be a presigned URL
        For local storage, this returns the file path
        """
        if self.settings.should_use_cloud_storage and HAS_BOTO3:
            # Generate presigned URL for temporary access
            try:
                return self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.settings.r2_bucket_name,
                        'Key': file_path
                    },
                    ExpiresIn=3600  # 1 hour
                )
            except Exception:
                return file_path
        else:
            return file_path


# Global storage service instance
storage_service = StorageService()
storage = storage_service  # Alias for backwards compatibility 