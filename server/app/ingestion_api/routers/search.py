from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.ingestion_api.models.schemas import SearchRequest, SearchResponse, SearchResult
from app.ingestion_api.dependencies import require_admin_user

router = APIRouter(prefix="/api/v1/search", tags=["Search"], dependencies=[Depends(require_admin_user)])


def _get_pipeline():
    from app.main import app
    return app.state.pipeline


@router.post("/", response_model=SearchResponse)
async def search_default(
    request: SearchRequest,
    collection_name: Optional[str] = Query(None),
):
    pipeline = _get_pipeline()
    from app.ingestion_api.config import app_config

    col_name = collection_name or app_config.default_collection
    if not pipeline.chroma_service.collection_exists(col_name):
        raise HTTPException(status_code=404, detail=f"Collection '{col_name}' not found")

    try:
        query_embedding = pipeline.embedding_service.embed_query(request.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")

    try:
        results = pipeline.chroma_service.query_collection(
            collection_name=col_name,
            query_embedding=query_embedding,
            n_results=request.n_results,
            where=request.where,
            where_document=request.where_document,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    search_results = [
        SearchResult(
            chunk_id=r["chunk_id"],
            document_text=r["document_text"],
            metadata=r["metadata"],
            distance=r.get("distance") if request.include_distances else None,
        )
        for r in results
    ]

    return SearchResponse(query=request.query, collection=col_name, total_results=len(search_results), results=search_results)


@router.post("/{collection_name}", response_model=SearchResponse)
async def search_collection(collection_name: str, request: SearchRequest):
    pipeline = _get_pipeline()
    if not pipeline.chroma_service.collection_exists(collection_name):
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")

    try:
        query_embedding = pipeline.embedding_service.embed_query(request.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")

    try:
        results = pipeline.chroma_service.query_collection(
            collection_name=collection_name,
            query_embedding=query_embedding,
            n_results=request.n_results,
            where=request.where,
            where_document=request.where_document,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

    search_results = [
        SearchResult(
            chunk_id=r["chunk_id"],
            document_text=r["document_text"],
            metadata=r["metadata"],
            distance=r.get("distance") if request.include_distances else None,
        )
        for r in results
    ]

    return SearchResponse(query=request.query, collection=collection_name, total_results=len(search_results), results=search_results)
