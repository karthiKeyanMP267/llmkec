from fastapi import APIRouter, Depends, HTTPException

from app.ingestion_api.config import app_config
from app.ingestion_api.models.schemas import (
    ChunkingConfigUpdateRequest,
    ConfigResponse,
    EmbeddingModelInfo,
    EmbeddingModelUpdateRequest,
)
from app.ingestion_api.dependencies import require_admin_user

router = APIRouter(prefix="/api/v1/config", tags=["Configuration"], dependencies=[Depends(require_admin_user)])


def _get_pipeline():
    from app.main import app
    return app.state.pipeline


@router.get("/", response_model=ConfigResponse)
async def get_config():
    return ConfigResponse(**app_config.to_dict())


@router.get("/models", response_model=list[EmbeddingModelInfo])
async def list_models():
    models = app_config.list_available_models()
    return [EmbeddingModelInfo(**m) for m in models]


@router.put("/embedding-model", response_model=EmbeddingModelInfo)
async def update_embedding_model(request: EmbeddingModelUpdateRequest):
    pipeline = _get_pipeline()
    try:
        model_info = pipeline.embedding_service.switch_model(request.model_key)
        return EmbeddingModelInfo(**model_info)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to switch model: {e}")


@router.put("/chunking")
async def update_chunking(request: ChunkingConfigUpdateRequest):
    pipeline = _get_pipeline()
    try:
        if request.chunk_size is not None:
            app_config.chunk_size = request.chunk_size
        if request.chunk_overlap is not None:
            if request.chunk_overlap >= (request.chunk_size or app_config.chunk_size):
                raise ValueError("Chunk overlap must be less than chunk size")
            app_config.chunk_overlap = request.chunk_overlap
        pipeline.chunking_service.update_params(app_config.chunk_size, app_config.chunk_overlap)
        return {
            "chunk_size": app_config.chunk_size,
            "chunk_overlap": app_config.chunk_overlap,
            "message": "Chunking parameters updated.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
