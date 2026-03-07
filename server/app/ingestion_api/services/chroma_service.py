import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from chromadb import PersistentClient
from chromadb.errors import InvalidArgumentError
from chromadb.utils import embedding_functions

from app.ingestion_api.utils.logger import get_logger

logger = get_logger("chroma_service")


class ChromaService:
    def __init__(self, chroma_data_dir: str):
        self.client = self._open_or_recover(chroma_data_dir)

    @staticmethod
    def _open_or_recover(chroma_data_dir: str) -> PersistentClient:
        """Open ChromaDB, auto-recovering from a malformed database if needed."""
        try:
            return PersistentClient(path=chroma_data_dir)
        except Exception as exc:
            if "malformed" not in str(exc).lower():
                raise
            logger.warning(
                "ChromaDB at '%s' is malformed. Backing up and recreating.",
                chroma_data_dir,
            )
            db_path = Path(chroma_data_dir)
            backup = db_path.with_name(db_path.name + "_corrupt_backup")
            if backup.exists():
                shutil.rmtree(backup)
            if db_path.exists():
                shutil.copytree(db_path, backup)
                # Remove all files so ChromaDB starts fresh
                shutil.rmtree(db_path)
                db_path.mkdir(parents=True, exist_ok=True)
            logger.info(
                "Corrupt DB backed up to '%s'. Creating fresh database.", backup
            )
            return PersistentClient(path=chroma_data_dir)

    def _get_collection(self, name: str):
        return self.client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})

    def list_collections(self) -> List[Dict[str, Any]]:
        cols = self.client.list_collections()
        out = []
        for c in cols:
            info = self.get_collection_info(c.name)
            out.append(info)
        return out

    def collection_exists(self, name: str) -> bool:
        try:
            self.client.get_collection(name)
            return True
        except Exception:
            return False

    def get_collection_info(self, name: str) -> Dict[str, Any]:
        col = self._get_collection(name)
        count = col.count()
        sample = col.peek(limit=5)
        sample_docs = []
        if sample and sample.get("ids"):
            for i in range(min(5, len(sample["ids"]))):
                sample_docs.append({
                    "id": sample["ids"][i],
                    "metadata": sample["metadatas"][i] if sample.get("metadatas") else {},
                    "text": sample["documents"][i] if sample.get("documents") else "",
                })
        return {
            "name": name,
            "document_count": count,
            "metadata": col.metadata or {},
            "sample_documents": sample_docs,
        }

    def create_collection(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        # Chroma rejects empty metadata; ensure a stable default tag.
        safe_meta = metadata if metadata else {"source": "admin-ui"}
        col = self.client.get_or_create_collection(name=name, metadata=safe_meta)
        return self.get_collection_info(col.name)

    def delete_collection(self, name: str) -> int:
        try:
            col = self.client.get_collection(name)
            count = col.count()
            self.client.delete_collection(name)
            return count
        except Exception as e:
            logger.error("Failed to delete collection '%s': %s", name, e)
            return 0

    def reset_collection(self, name: str) -> int:
        col = self._get_collection(name)
        count = col.count()
        if count > 0:
            all_ids = col.get(include=[])["ids"]
            if all_ids:
                col.delete(ids=all_ids)
        return count

    def rename_collection(self, old_name: str, new_name: str, new_metadata: Optional[Dict[str, Any]] = None):
        col = self.client.get_collection(old_name)
        target_name = new_name or old_name
        safe_meta = new_metadata if new_metadata is not None else (col.metadata or {"source": "admin-ui"})
        col.modify(name=target_name, metadata=safe_meta)
        return self.get_collection_info(target_name)

    def add_documents(self, collection_name: str, embeddings: List[List[float]], documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        col = self._get_collection(collection_name)
        try:
            col.add(embeddings=embeddings, documents=documents, metadatas=metadatas, ids=ids)
        except InvalidArgumentError as exc:
            message = str(exc)
            if "Collection expecting embedding with dimension" in message:
                actual_dim = len(embeddings[0]) if embeddings and embeddings[0] else None
                msg = (f"Embedding dimension mismatch for collection '{collection_name}'. "
                       f"Collection was created with a different model/dimension. "
                       f"Current embedding dimension: {actual_dim}. "
                       f"Delete and recreate the collection (or switch back to the original embedding model), then re-ingest documents. "
                       f"Original error: {message}")
                logger.error(msg)
                return
            logger.error("Failed to add documents to collection '%s': %s", collection_name, exc)
            return

    def delete_document(self, collection_name: str, doc_id: str):
        col = self._get_collection(collection_name)
        before = col.count()
        col.delete(where={"doc_id": doc_id})
        after = col.count()
        return max(before - after, 0)

    def get_collection_documents(self, collection_name: str) -> List[Dict[str, Any]]:
        """Synthesize document-level entries from ChromaDB chunk metadata.

        Useful for collections ingested externally (e.g. via standalone ingest.py)
        where the MetadataStore has no records.  Groups chunks by source file and
        returns one entry per source file with chunk count.
        """
        try:
            col = self.client.get_collection(collection_name)
        except Exception:
            return []

        total = col.count()
        if total == 0:
            return []

        # Fetch all chunk metadata (no embeddings/documents to keep it light)
        data = col.get(include=["metadatas"], limit=total)
        metadatas = data.get("metadatas") or []

        # Group by source file
        source_map: Dict[str, Dict[str, Any]] = {}
        for m in metadatas:
            if not m:
                continue
            # Try common metadata keys used by different ingest pipelines
            src = (
                m.get("source_file")
                or m.get("file_name")
                or m.get("filename")
                or m.get("source")
                or "unknown"
            )
            if src not in source_map:
                source_map[src] = {
                    "doc_id": m.get("doc_id", src),
                    "filename": src,
                    "collection_name": collection_name,
                    "total_chunks": 0,
                    "total_pages": 0,
                    "file_size_bytes": int(m.get("file_size", 0) or 0),
                    "embedding_model": None,
                    "chunk_size": 0,
                    "chunk_overlap": 0,
                    "status": "completed",
                    "error_message": None,
                    "created_at": m.get("creation_date") or m.get("doc_date"),
                    "updated_at": m.get("last_modified_date") or m.get("doc_date"),
                    "_source": "chroma",
                }
            source_map[src]["total_chunks"] += 1

        return list(source_map.values())

    def query_collection(
        self,
        collection_name: str,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        col = self._get_collection(collection_name)
        res = col.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document,
        )
        out = []
        for i in range(len(res.get("ids", [[]])[0])):
            out.append(
                {
                    "chunk_id": res["ids"][0][i],
                    "document_text": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i],
                    "distance": res.get("distances", [[None]])[0][i],
                }
            )
        return out
