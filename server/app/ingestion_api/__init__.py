"""Integration entrypoint for the auto-ingestion pipeline inside the main FastAPI app.

Usage:
    from app.ingestion_api import register_ingestion
    register_ingestion(app)
"""

from fastapi import FastAPI

from app.ingestion_api.config import app_config
from app.ingestion_api.routers import collections, config_router, documents, search, health
from app.ingestion_api.services.ingestion_pipeline import (
    IngestionPipeline,
    MetadataStore,
)
from app.ingestion_api.services.chroma_service import ChromaService
from app.ingestion_api.services.chunking_service import ChunkingService
from app.ingestion_api.services.embedding_service import EmbeddingService
from app.ingestion_api.services.pdf_processor import PDFProcessorService
from app.ingestion_api.utils.file_utils import FileManager
from app.ingestion_api.utils.logger import get_logger

logger = get_logger("ingestion_api")


def _init_pipeline(app: FastAPI):
    """Initialize all ingestion services and attach to app.state."""
    pdf_processor = PDFProcessorService()
    chunking_service = ChunkingService(
        chunk_size=app_config.chunk_size,
        chunk_overlap=app_config.chunk_overlap,
    )
    embedding_service = EmbeddingService(config=app_config)
    chroma_service = ChromaService(chroma_data_dir=app_config.chroma_data_dir)
    file_manager = FileManager(uploads_dir=app_config.uploads_dir)
    metadata_store = MetadataStore(db_path=app_config.metadata_db_path)

    pipeline = IngestionPipeline(
        config=app_config,
        pdf_processor=pdf_processor,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        chroma_service=chroma_service,
        file_manager=file_manager,
        metadata_store=metadata_store,
    )

    app.state.pipeline = pipeline
    app.state.file_manager = file_manager

    logger.info("Ingestion pipeline initialized")
    logger.info("Embedding model: %s", app_config.current_model_name)
    logger.info("Chunk size: %s, overlap: %s", app_config.chunk_size, app_config.chunk_overlap)


def register_ingestion(app: FastAPI, prefix: str = ""):
    """Mount ingestion routes into an existing FastAPI app.

    Args:
        app: main FastAPI instance.
        prefix: optional path prefix for all ingestion routes (e.g., "/ingestion").
    """

    @app.on_event("startup")
    async def _startup_ingestion():
        _init_pipeline(app)

    @app.on_event("shutdown")
    async def _shutdown_ingestion():
        app.state.pipeline = None
        app.state.file_manager = None

    # Include routers with optional prefix
    app.include_router(health.router, prefix=prefix)
    app.include_router(documents.router, prefix=prefix)
    app.include_router(collections.router, prefix=prefix)
    app.include_router(search.router, prefix=prefix)
    app.include_router(config_router.router, prefix=prefix)

    logger.info("Ingestion API registered with prefix '%s'", prefix)
