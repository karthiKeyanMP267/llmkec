from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.ingestion_api.models.enums import IngestionStatus
from app.ingestion_api.utils.logger import get_logger

logger = get_logger(__name__)


class DocumentMetadata(BaseModel):
    doc_id: str = Field(...)
    filename: str = Field(...)
    collection_name: str = Field(...)
    total_chunks: int = Field(0)
    total_pages: int = Field(0)
    file_size_bytes: int = Field(0)
    embedding_model: str = Field(...)
    chunk_size: int = Field(...)
    chunk_overlap: int = Field(...)
    status: IngestionStatus = Field(IngestionStatus.PENDING)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    collection_name: str
    status: IngestionStatus
    message: str


class DocumentListResponse(BaseModel):
    total: int
    documents: List[DocumentMetadata]


class DocumentDetailResponse(BaseModel):
    metadata: DocumentMetadata
    sample_chunks: List[Dict[str, Any]] = Field(default_factory=list)


class DocumentDeleteResponse(BaseModel):
    doc_id: str
    filename: str
    chunks_deleted: int
    message: str


class DocumentStatusResponse(BaseModel):
    doc_id: str
    filename: str
    status: IngestionStatus
    total_chunks: int
    error_message: Optional[str] = None


class BatchUploadResponse(BaseModel):
    total_files: int
    accepted: int
    rejected: int
    documents: List[DocumentUploadResponse]
    errors: List[Dict[str, str]] = Field(default_factory=list)


class CollectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            logger.error("Invalid collection name: %s", v)
            raise ValueError("Collection name must be alphanumeric/underscore/hyphen")  # raise required by Pydantic
        return v


class CollectionInfo(BaseModel):
    name: str
    document_count: int
    metadata: Optional[Dict[str, Any]] = None
    sample_documents: List[Dict[str, Any]] = Field(default_factory=list)


class CollectionListResponse(BaseModel):
    total: int
    collections: List[CollectionInfo]


class CollectionUpdateRequest(BaseModel):
    new_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CollectionDeleteResponse(BaseModel):
    name: str
    documents_removed: int
    message: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    n_results: int = Field(10, ge=1, le=100)
    where: Optional[Dict[str, Any]] = None
    where_document: Optional[Dict[str, Any]] = None
    include_distances: bool = True


class SearchResult(BaseModel):
    chunk_id: str
    document_text: str
    metadata: Dict[str, Any]
    distance: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    collection: str
    total_results: int
    results: List[SearchResult]


class EmbeddingModelInfo(BaseModel):
    key: str
    model_name: str
    dimensions: int
    description: str
    is_current: bool


class EmbeddingModelUpdateRequest(BaseModel):
    model_key: str = Field(...)


class ChunkingConfigUpdateRequest(BaseModel):
    chunk_size: Optional[int] = Field(None, ge=64, le=4096)
    chunk_overlap: Optional[int] = Field(None, ge=0)


class ConfigResponse(BaseModel):
    embedding_model: Dict[str, Any]
    chunking: Dict[str, Any]
    paths: Dict[str, str]
    default_collection: str
    server: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str
    chroma_connected: bool
    collections_count: int
    current_embedding_model: str
