"""
Launcher for the ingestion FastAPI app that honors environment overrides.

Environment variables:
- API_HOST / API_PORT: bind address and port (defaults: 0.0.0.0 / 8000)
- API_RELOAD: set to true to enable auto-reload in development
- CHROMA_DATA_DIR, UPLOADS_DIR, METADATA_DB_PATH, DEFAULT_COLLECTION, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP
"""

import os

import uvicorn

from app.ingestion_api.config import app_config


def main():
    reload_enabled = os.getenv("API_RELOAD", "false").lower() in {"1", "true", "yes", "on"}
    uvicorn.run(
        "app.main:app",
        host=app_config.host,
        port=app_config.port,
        reload=reload_enabled,
    )


if __name__ == "__main__":
    main()
