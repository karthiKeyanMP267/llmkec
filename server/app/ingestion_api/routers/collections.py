from fastapi import APIRouter, Depends, HTTPException

from app.ingestion_api.models.schemas import (
    CollectionCreateRequest,
    CollectionDeleteResponse,
    CollectionInfo,
    CollectionListResponse,
    CollectionUpdateRequest,
)
from app.ingestion_api.dependencies import require_admin_user

router = APIRouter(prefix="/api/v1/collections", tags=["Collections"], dependencies=[Depends(require_admin_user)])


def _get_pipeline():
    from app.main import app
    return app.state.pipeline


@router.get("/", response_model=CollectionListResponse)
async def list_collections():
    pipeline = _get_pipeline()
    collections = pipeline.chroma_service.list_collections()
    col_list = [
        CollectionInfo(
            name=c["name"],
            document_count=c["document_count"],
            metadata=c.get("metadata"),
        )
        for c in collections
    ]
    return CollectionListResponse(total=len(col_list), collections=col_list)


@router.post("/", response_model=CollectionInfo, status_code=201)
async def create_collection(request: CollectionCreateRequest):
    pipeline = _get_pipeline()
    try:
        result = pipeline.chroma_service.create_collection(name=request.name, metadata=request.metadata)
        return CollectionInfo(
            name=result["name"],
            document_count=result["document_count"],
            metadata=result.get("metadata"),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{name}", response_model=CollectionInfo)
async def get_collection(name: str):
    pipeline = _get_pipeline()
    if not pipeline.chroma_service.collection_exists(name):
        raise HTTPException(status_code=404, detail=f"Collection '{name}' not found")
    info = pipeline.chroma_service.get_collection_info(name)
    return CollectionInfo(
        name=info["name"],
        document_count=info["document_count"],
        metadata=info.get("metadata"),
        sample_documents=info.get("sample_documents", []),
    )


@router.put("/{name}", response_model=CollectionInfo)
async def update_collection(name: str, request: CollectionUpdateRequest):
    pipeline = _get_pipeline()
    if not pipeline.chroma_service.collection_exists(name):
        raise HTTPException(status_code=404, detail=f"Collection '{name}' not found")
    try:
        result = pipeline.chroma_service.rename_collection(
            old_name=name,
            new_name=request.new_name,
            new_metadata=request.metadata,
        )
        return CollectionInfo(
            name=result["name"],
            document_count=result["document_count"],
            metadata=result.get("metadata"),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{name}", response_model=CollectionDeleteResponse)
async def delete_collection(name: str):
    pipeline = _get_pipeline()
    if not pipeline.chroma_service.collection_exists(name):
        raise HTTPException(status_code=404, detail=f"Collection '{name}' not found")
    count = pipeline.chroma_service.delete_collection(name)
    return CollectionDeleteResponse(
        name=name,
        documents_removed=count,
        message=f"Collection '{name}' deleted with {count} documents.",
    )


@router.post("/{name}/reset", response_model=CollectionDeleteResponse)
async def reset_collection(name: str):
    pipeline = _get_pipeline()
    if not pipeline.chroma_service.collection_exists(name):
        raise HTTPException(status_code=404, detail=f"Collection '{name}' not found")
    count = pipeline.chroma_service.reset_collection(name)
    return CollectionDeleteResponse(
        name=name,
        documents_removed=count,
        message=f"Collection '{name}' reset. {count} documents removed.",
    )
