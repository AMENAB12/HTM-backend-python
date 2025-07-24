from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .api.routes import auth, files, health

# Get settings instance
config_settings = get_settings()

app = FastAPI(
    title=config_settings.app_name, 
    version=config_settings.app_version,
    description="A FastAPI backend for uploading CSV files and converting them to Parquet format"
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=config_settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 