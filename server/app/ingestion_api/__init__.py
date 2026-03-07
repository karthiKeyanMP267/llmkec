"""Integration entrypoint for the auto-ingestion pipeline inside the main FastAPI app.

Usage:
    from app.ingestion_api import register_ingestion, create_ingestion_app
    register_ingestion(app)

    # Or create a standalone sub-app for a specific ChromaDB store:
    sub = create_ingestion_app(chroma_data_dir="/path/to/store")
    app.mount("/ingestion/faculty", sub)
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.ingestion_api.config import app_config, AppConfig
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


def _build_pipeline(chroma_data_dir: str = None, uploads_dir: str = None, metadata_db_path: str = None):
    """Build an IngestionPipeline with optional overrides for storage paths."""
    effective_chroma = chroma_data_dir or app_config.chroma_data_dir
    effective_uploads = uploads_dir or app_config.uploads_dir
    effective_metadata = metadata_db_path or app_config.metadata_db_path

    # Ensure directories exist
    Path(effective_chroma).mkdir(parents=True, exist_ok=True)
    Path(effective_uploads).mkdir(parents=True, exist_ok=True)
    Path(effective_metadata).parent.mkdir(parents=True, exist_ok=True)

    pdf_processor = PDFProcessorService(api_key=app_config.llama_parse_api_key)
    chunking_service = ChunkingService(
        chunk_size=app_config.chunk_size,
        chunk_overlap=app_config.chunk_overlap,
    )
    embedding_service = EmbeddingService(config=app_config)
    chroma_service = ChromaService(chroma_data_dir=effective_chroma)
    file_manager = FileManager(uploads_dir=effective_uploads)
    metadata_store = MetadataStore(db_path=effective_metadata)

    pipeline = IngestionPipeline(
        config=app_config,
        pdf_processor=pdf_processor,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        chroma_service=chroma_service,
        file_manager=file_manager,
        metadata_store=metadata_store,
    )

    return pipeline, file_manager


def _init_pipeline(app: FastAPI, chroma_data_dir: str = None):
    """Initialize all ingestion services and attach to app.state."""
    pipeline, file_manager = _build_pipeline(chroma_data_dir=chroma_data_dir)

    app.state.pipeline = pipeline
    app.state.file_manager = file_manager

    logger.info("Ingestion pipeline initialized (chroma=%s)", pipeline.chroma_service.client._identifier if hasattr(pipeline.chroma_service.client, '_identifier') else chroma_data_dir or app_config.chroma_data_dir)
    logger.info("Embedding model: %s", app_config.current_model_name)
    logger.info("Chunk size: %s, overlap: %s", app_config.chunk_size, app_config.chunk_overlap)


def create_ingestion_app(chroma_data_dir: str = None, uploads_dir: str = None, metadata_db_path: str = None) -> FastAPI:
    """Create a standalone FastAPI sub-application with its own ingestion pipeline.

    Each sub-app gets its own ChromaService pointing to `chroma_data_dir`,
    so requests routed through this sub-app only see that store.
    """
    from fastapi.middleware.cors import CORSMiddleware

    @asynccontextmanager
    async def _lifespan(application: FastAPI):
        pipeline, file_manager = _build_pipeline(
            chroma_data_dir=chroma_data_dir,
            uploads_dir=uploads_dir,
            metadata_db_path=metadata_db_path,
        )
        application.state.pipeline = pipeline
        application.state.file_manager = file_manager
        logger.info("Sub-app ingestion pipeline initialized (chroma=%s)", chroma_data_dir or app_config.chroma_data_dir)
        yield
        application.state.pipeline = None
        application.state.file_manager = None

    sub = FastAPI(title="KEC Ingestion Sub-App", lifespan=_lifespan)
    sub.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    sub.include_router(health.router)
    sub.include_router(documents.router)
    sub.include_router(collections.router)
    sub.include_router(search.router)
    sub.include_router(config_router.router)

    return sub


def register_ingestion(app: FastAPI, prefix: str = "", chroma_data_dir: str = None):
    """Mount ingestion routes into an existing FastAPI app.

    Args:
        app: main FastAPI instance.
        prefix: optional path prefix for all ingestion routes (e.g., "/ingestion").
        chroma_data_dir: optional override for ChromaDB storage path.
    """

    @app.on_event("startup")
    async def _startup_ingestion():
        _init_pipeline(app, chroma_data_dir=chroma_data_dir)

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
