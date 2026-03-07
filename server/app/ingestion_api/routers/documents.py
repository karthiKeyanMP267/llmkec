from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse

from app.ingestion_api.models.enums import IngestionStatus
from app.ingestion_api.models.schemas import (
    BatchUploadResponse,
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentMetadata,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.ingestion_api.utils.logger import get_logger
from app.ingestion_api.dependencies import require_admin_user, get_pipeline, get_file_manager

logger = get_logger("router.documents")

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"], dependencies=[Depends(require_admin_user)])


def _sanitize_meta(meta: dict) -> dict:
    # Normalize legacy/partial rows so Pydantic validators accept them.
    meta = dict(meta or {})
    meta["total_chunks"] = int(meta.get("total_chunks") or 0)
    meta["total_pages"] = int(meta.get("total_pages") or 0)
    meta["file_size_bytes"] = int(meta.get("file_size_bytes") or 0)
    meta["chunk_size"] = int(meta.get("chunk_size") or 0)
    meta["chunk_overlap"] = int(meta.get("chunk_overlap") or 0)
    # Ensure embedding_model is a string or None (not 0/False)
    em = meta.get("embedding_model")
    meta["embedding_model"] = str(em) if em else None
    # Ensure datetime fields are valid or None
    for dt_key in ("created_at", "updated_at"):
        val = meta.get(dt_key)
        if val is None or val == "":
            meta[dt_key] = None
    return meta


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection_name: Optional[str] = Query(None),
    pipeline=Depends(get_pipeline),
    file_manager=Depends(get_file_manager),
):

    content = await file.read()
    is_valid, error = file_manager.validate_pdf(file.filename, content)
    if not is_valid:
        logger.error("Upload validation failed for '%s': %s", file.filename, error)
        return JSONResponse(status_code=400, content={"detail": error})

    from app.ingestion_api.config import app_config
    col_name = collection_name or app_config.default_collection

    doc_id = file_manager.generate_doc_id()
    file_path = await file_manager.save_upload(content, file.filename, doc_id)

    pipeline.register_document(doc_id, file.filename, col_name, len(content))
    background_tasks.add_task(pipeline.process_document, doc_id, file_path, col_name)

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        collection_name=col_name,
        status=IngestionStatus.PENDING,
        message="PDF uploaded successfully. Processing started in background.",
    )


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def batch_upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    collection_name: Optional[str] = Query(None),
    pipeline=Depends(get_pipeline),
    file_manager=Depends(get_file_manager),
):
    from app.ingestion_api.config import app_config

    col_name = collection_name or app_config.default_collection
    documents = []
    errors = []
    accepted = 0
    rejected = 0

    for file in files:
        content = await file.read()
        is_valid, error = file_manager.validate_pdf(file.filename, content)
        if not is_valid:
            rejected += 1
            errors.append({"filename": file.filename, "error": error})
            continue
        doc_id = file_manager.generate_doc_id()
        file_path = await file_manager.save_upload(content, file.filename, doc_id)
        pipeline.register_document(doc_id, file.filename, col_name, len(content))
        background_tasks.add_task(pipeline.process_document, doc_id, file_path, col_name)
        documents.append(
            DocumentUploadResponse(
                doc_id=doc_id,
                filename=file.filename,
                collection_name=col_name,
                status=IngestionStatus.PENDING,
                message="Queued for processing.",
            )
        )
        accepted += 1

    return BatchUploadResponse(
        total_files=len(files),
        accepted=accepted,
        rejected=rejected,
        documents=documents,
        errors=errors,
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(collection_name: Optional[str] = Query(None), pipeline=Depends(get_pipeline)):
    # Get documents from MetadataStore (admin-uploaded docs)
    meta_docs = pipeline.metadata_store.get_all_documents(collection_name)
    safe_docs = [_sanitize_meta(d) for d in meta_docs]

    # Always merge with ChromaDB-synthetic entries so that documents ingested
    # via standalone scripts (faculty JSON, student PDFs) also appear.
    try:
        chroma_docs = []
        if collection_name:
            chroma_docs = pipeline.chroma_service.get_collection_documents(collection_name)
        else:
            for col_info in pipeline.chroma_service.list_collections():
                chroma_docs.extend(
                    pipeline.chroma_service.get_collection_documents(col_info["name"])
                )
        # Deduplicate: MetadataStore entries win if same filename exists in both
        existing_filenames = {d.get("filename") for d in safe_docs}
        for cd in chroma_docs:
            if cd.get("filename") not in existing_filenames:
                safe_docs.append(_sanitize_meta(cd))
    except Exception as exc:
        logger.warning("ChromaDB document merge failed: %s", exc)

    return DocumentListResponse(total=len(safe_docs), documents=[DocumentMetadata(**d) for d in safe_docs])


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(doc_id: str, pipeline=Depends(get_pipeline)):
    doc = pipeline.metadata_store.get_document(doc_id)
    if not doc:
        # Fallback: look up by source filename in ChromaDB collections
        try:
            for col_info in pipeline.chroma_service.list_collections():
                chroma_docs = pipeline.chroma_service.get_collection_documents(col_info["name"])
                for cd in chroma_docs:
                    if cd.get("doc_id") == doc_id or cd.get("filename") == doc_id:
                        doc = cd
                        break
                if doc:
                    break
        except Exception:
            pass
    if not doc:
        logger.error("Document %s not found", doc_id)
        return JSONResponse(status_code=404, content={"detail": f"Document {doc_id} not found"})
    sample_chunks = []
    if doc.get("status") in (IngestionStatus.COMPLETED.value, "completed"):
        try:
            sample_chunks = pipeline.get_document_chunks(
                doc.get("doc_id", doc_id),
                doc["collection_name"],
                limit=5,
            )
        except Exception:
            # For externally ingested docs, get_document_chunks may fail on
            # the 'where' filter if doc_id doesn't match chunk metadata.
            # Fall back to a simple collection peek.
            try:
                col_info = pipeline.chroma_service.get_collection_info(doc["collection_name"])
                sample_chunks = [
                    {"chunk_id": s["id"], "document_text": s.get("text", ""), "metadata": s.get("metadata", {})}
                    for s in col_info.get("sample_documents", [])
                ]
            except Exception:
                pass
    return DocumentDetailResponse(metadata=DocumentMetadata(**_sanitize_meta(doc)), sample_chunks=sample_chunks)


@router.get("/{doc_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(doc_id: str, pipeline=Depends(get_pipeline)):
    doc = pipeline.metadata_store.get_document(doc_id)
    if not doc:
        logger.error("Document %s not found for status check", doc_id)
        return JSONResponse(status_code=404, content={"detail": f"Document {doc_id} not found"})
    safe = _sanitize_meta(doc)
    return DocumentStatusResponse(
        doc_id=safe["doc_id"],
        filename=safe["filename"],
        status=IngestionStatus(safe["status"]),
        total_chunks=safe["total_chunks"],
        error_message=safe.get("error_message"),
    )


@router.put("/{doc_id}", response_model=DocumentUploadResponse)
async def replace_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection_name: Optional[str] = Query(None),
    pipeline=Depends(get_pipeline),
    file_manager=Depends(get_file_manager),
):

    doc = pipeline.metadata_store.get_document(doc_id)
    if not doc:
        logger.error("Document %s not found for replacement", doc_id)
        return JSONResponse(status_code=404, content={"detail": f"Document {doc_id} not found"})

    content = await file.read()
    is_valid, error = file_manager.validate_pdf(file.filename, content)
    if not is_valid:
        logger.error("Replacement file validation failed for '%s': %s", file.filename, error)
        return JSONResponse(status_code=400, content={"detail": error})

    col_name = collection_name or doc["collection_name"]
    file_path = await file_manager.save_upload(content, file.filename, doc_id)
    pipeline.metadata_store.update_status(doc_id, IngestionStatus.PENDING.value)
    background_tasks.add_task(pipeline.replace_document, doc_id, file_path, col_name)

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        collection_name=col_name,
        status=IngestionStatus.PENDING,
        message="Document replacement queued.",
    )


@router.delete("/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(doc_id: str, pipeline=Depends(get_pipeline)):
    doc = pipeline.metadata_store.get_document(doc_id)
    if not doc:
        logger.error("Document %s not found for deletion", doc_id)
        return JSONResponse(status_code=404, content={"detail": f"Document {doc_id} not found"})
    result = pipeline.delete_document(doc_id)
    return DocumentDeleteResponse(
        doc_id=result["doc_id"],
        filename=result["filename"],
        chunks_deleted=int(result.get("chunks_deleted", 0)),
        message="Document and all chunks deleted successfully.",
    )
