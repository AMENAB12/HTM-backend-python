import os
from typing import Optional
try:
    from pydantic_settings import BaseSettings
    from pydantic import field_validator
except ImportError:
    from pydantic import BaseSettings, validator as field_validator

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # API Configuration
    app_name: str = "CSV to Parquet Converter API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    
    # Database Configuration
    database_path: str = "metadata.db"
    
    # File Storage Configuration
    upload_dir: str = "uploads"
    parquet_dir: str = "parquet"
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_extensions: list = [".csv"]
    
    # Authentication Configuration
    jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days (7 * 24 * 60)
    
    # Processing Configuration
    processing_delay_seconds: int = 3
    
    # CORS Configuration
    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    
    @field_validator('jwt_secret_key')
    @classmethod
    def validate_jwt_secret_key(cls, v):
        if v is None:
            import secrets
            return secrets.token_urlsafe(32)
        return v
    
    @field_validator('upload_dir', 'parquet_dir')
    @classmethod
    def create_directories(cls, v):
        os.makedirs(v, exist_ok=True)
        return v
    
    def get_cors_origins_list(self) -> list:
        """Parse CORS origins string into a list"""
        if isinstance(self.cors_origins, list):
            return self.cors_origins
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields from .env

# Create global settings instance
settings = Settings()

# Environment-specific configurations
def get_settings() -> Settings:
    """Get application settings"""
    return settings

def is_development() -> bool:
    """Check if running in development mode"""
    return settings.debug or os.getenv("ENVIRONMENT", "development") == "development"

def is_production() -> bool:
    """Check if running in production mode"""
    return not is_development() 