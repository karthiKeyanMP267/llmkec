from fastapi import APIRouter

from app.ingestion_api.config import app_config
from app.ingestion_api.models.schemas import HealthResponse
from app.ingestion_api.utils.logger import get_logger

logger = get_logger("router.health")

router = APIRouter(tags=["Health"])


def _get_pipeline():
    from app.main import app
    return getattr(app.state, "pipeline", None)


@router.get("/health", response_model=HealthResponse)
async def healthcheck():
    pipeline = _get_pipeline()
    chroma_ok = False
    collections_count = 0

    if pipeline:
        try:
            collections = pipeline.chroma_service.list_collections()
            collections_count = len(collections)
            chroma_ok = True
        except Exception as exc:  # pragma: no cover - defensive log path
            logger.warning("Chroma health check failed: %s", exc)

    return HealthResponse(
        status="healthy" if chroma_ok else "degraded",
        version="1.0.0",
        chroma_connected=chroma_ok,
        collections_count=collections_count,
        current_embedding_model=app_config.current_model_name,
    )