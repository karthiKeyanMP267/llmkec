"""
Launcher for the ingestion FastAPI app that honors environment overrides.

Environment variables:
- API_HOST / API_PORT: bind address and port (defaults: 0.0.0.0 / 8000)
- API_RELOAD: set to true to enable auto-reload in development
- CHROMA_DATA_DIR, UPLOADS_DIR, METADATA_DB_PATH, DEFAULT_COLLECTION, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP
"""

import logging
import os

import uvicorn

from app.ingestion_api.config import app_config

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    reload_enabled = os.getenv("API_RELOAD", "false").lower() in {"1", "true", "yes", "on"}
    logger.info("Starting ingestion API on %s:%d (reload=%s)", app_config.host, app_config.port, reload_enabled)
    uvicorn.run(
        "app.main:app",
        host=app_config.host,
        port=app_config.port,
        reload=reload_enabled,
    )


if __name__ == "__main__":
    main()
