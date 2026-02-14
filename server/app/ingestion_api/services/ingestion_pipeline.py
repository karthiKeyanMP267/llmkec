import sqlite3
import time
from typing import Any, Dict, List, Tuple

from app.ingestion_api.config import AppConfig, app_config
from app.ingestion_api.models.enums import IngestionStatus
from app.ingestion_api.utils.logger import get_logger

logger = get_logger("ingestion_pipeline")


class MetadataStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    filename TEXT,
                    collection_name TEXT,
                    total_chunks INTEGER,
                    total_pages INTEGER,
                    file_size_bytes INTEGER,
                    embedding_model TEXT,
                    chunk_size INTEGER,
                    chunk_overlap INTEGER,
                    status TEXT,
                    error_message TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.commit()

    def _row_to_dict(self, row) -> Dict[str, Any]:
        if not row:
            return None
        keys = [
            "doc_id",
            "filename",
            "collection_name",
            "total_chunks",
            "total_pages",
            "file_size_bytes",
            "embedding_model",
            "chunk_size",
            "chunk_overlap",
            "status",
            "error_message",
            "created_at",
            "updated_at",
        ]
        return {k: row[i] for i, k in enumerate(keys)}

    def upsert_document(self, meta: Dict[str, Any]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents
                (doc_id, filename, collection_name, total_chunks, total_pages, file_size_bytes, embedding_model, chunk_size, chunk_overlap, status, error_message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meta["doc_id"],
                    meta["filename"],
                    meta["collection_name"],
                    meta.get("total_chunks", 0),
                    meta.get("total_pages", 0),
                    meta.get("file_size_bytes", 0),
                    meta.get("embedding_model"),
                    meta.get("chunk_size"),
                    meta.get("chunk_overlap"),
                    meta.get("status"),
                    meta.get("error_message"),
                    meta.get("created_at"),
                    meta.get("updated_at"),
                ),
            )
            conn.commit()

    def get_document(self, doc_id: str):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,))
            row = cur.fetchone()
            return self._row_to_dict(row)

    def get_all_documents(self, collection_name: str = None):
        with sqlite3.connect(self.db_path) as conn:
            if collection_name:
                cur = conn.execute("SELECT * FROM documents WHERE collection_name=?", (collection_name,))
            else:
                cur = conn.execute("SELECT * FROM documents")
            return [self._row_to_dict(r) for r in cur.fetchall()]

    def delete_document(self, doc_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
            conn.commit()

    def update_status(self, doc_id: str, status: str, error_message: str = None, total_chunks: int = None):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE documents SET status=?, error_message=?, total_chunks=?, updated_at=? WHERE doc_id=?",
                (status, error_message, total_chunks, time.strftime("%Y-%m-%d %H:%M:%S"), doc_id),
            )
            conn.commit()


class IngestionPipeline:
    def __init__(
        self,
        config: AppConfig,
        pdf_processor,
        chunking_service,
        embedding_service,
        chroma_service,
        file_manager,
        metadata_store: MetadataStore,
    ):
        self.config = config
        self.pdf_processor = pdf_processor
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.chroma_service = chroma_service
        self.file_manager = file_manager
        self.metadata_store = metadata_store

    def register_document(self, doc_id: str, filename: str, collection_name: str, file_size_bytes: int):
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        self.metadata_store.upsert_document(
            {
                "doc_id": doc_id,
                "filename": filename,
                "collection_name": collection_name,
                "total_chunks": 0,
                "total_pages": 0,
                "file_size_bytes": file_size_bytes,
                "embedding_model": self.config.current_model_key,
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
                "status": IngestionStatus.PENDING.value,
                "error_message": None,
                "created_at": now,
                "updated_at": now,
            }
        )

    def _process(self, doc_id: str, file_path: str, collection_name: str):
        # Parse PDF with LlamaParse and chunk via llama-index
        documents, pages = self.pdf_processor.extract(file_path)
        if not documents:
            raise ValueError("No parseable content found in PDF")

        chunks = self.chunking_service.chunk_documents(documents)
        docs = [c.get_content() for c in chunks]
        if not docs:
            raise ValueError("No chunks generated from parsed PDF content")

        # Embed
        embeddings = self.embedding_service.embed_documents(docs)
        if not embeddings:
            raise ValueError("Embedding generation returned empty output")

        # Prepare metadata for each chunk
        metadatas = []
        chunk_ids = []
        for i, c in enumerate(chunks):
            cid = f"{doc_id}_chunk_{i}"
            chunk_ids.append(cid)
            page_label = c.metadata.get("page_label") if isinstance(c.metadata, dict) else None
            safe_meta = {
                "doc_id": doc_id,
                "chunk_index": i,
                "collection_name": collection_name,
            }
            if page_label is not None:
                safe_meta["page_label"] = str(page_label)
            metadatas.append(safe_meta)

        # Store in Chroma
        self.chroma_service.add_documents(collection_name, embeddings, docs, metadatas, chunk_ids)

        # Update metadata
        self.metadata_store.update_status(doc_id, IngestionStatus.COMPLETED.value, None, len(chunks))
        with sqlite3.connect(self.metadata_store.db_path) as conn:
            conn.execute(
                "UPDATE documents SET total_pages=? WHERE doc_id=?",
                (pages, doc_id),
            )
            conn.commit()

    def process_document(self, doc_id: str, file_path: str, collection_name: str):
        try:
            self.metadata_store.update_status(doc_id, IngestionStatus.PROCESSING.value)
            self._process(doc_id, file_path, collection_name)
        except Exception as e:
            logger.exception("Processing failed for %s", doc_id)
            self.metadata_store.update_status(doc_id, IngestionStatus.FAILED.value, str(e))
        finally:
            self.file_manager.delete_file(file_path)

    def replace_document(self, doc_id: str, file_path: str, collection_name: str):
        # Delete existing chunks
        self.chroma_service.delete_document(collection_name, doc_id)
        # Re-process new file
        self.process_document(doc_id, file_path, collection_name)

    def delete_document(self, doc_id: str) -> Dict[str, Any]:
        doc = self.metadata_store.get_document(doc_id)
        if not doc:
            raise ValueError("Document not found")
        chunks_deleted = self.chroma_service.delete_document(doc["collection_name"], doc_id)
        self.metadata_store.delete_document(doc_id)
        return {"doc_id": doc_id, "filename": doc.get("filename"), "chunks_deleted": chunks_deleted or 0}

    def get_document_chunks(self, doc_id: str, collection_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        # Fetch sample chunks from the document's collection so preview respects tenancy.
        results = self.chroma_service.query_collection(
            collection_name=collection_name,
            query_embedding=self.embedding_service.embed_query("sample"),
            n_results=limit,
            where={"doc_id": doc_id},
        )
        return results
