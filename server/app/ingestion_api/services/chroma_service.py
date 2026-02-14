import json
from typing import Any, Dict, List, Optional

from chromadb import PersistentClient
from chromadb.utils import embedding_functions

from app.ingestion_api.utils.logger import get_logger

logger = get_logger("chroma_service")


class ChromaService:
    def __init__(self, chroma_data_dir: str):
        self.client = PersistentClient(path=chroma_data_dir)

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
        meta = col.get(ids=None, limit=5)
        return {
            "name": name,
            "document_count": len(meta["ids"]) if meta and meta.get("ids") else 0,
            "metadata": col.metadata or {},
            "sample_documents": [
                {
                    "id": meta["ids"][i],
                    "metadata": meta["metadatas"][i],
                    "text": meta["documents"][i],
                }
                for i in range(min(5, len(meta.get("ids", []))))
            ],
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
            raise e

    def reset_collection(self, name: str) -> int:
        col = self._get_collection(name)
        count = col.count()
        col.delete(where={})
        return count

    def rename_collection(self, old_name: str, new_name: str, new_metadata: Optional[Dict[str, Any]] = None):
        old = self._get_collection(old_name)
        data = old.get()
        self.client.delete_collection(old_name)
        safe_meta = new_metadata if new_metadata else {"source": "admin-ui"}
        new_col = self.client.get_or_create_collection(name=new_name, metadata=safe_meta)
        if data and data.get("ids"):
            new_col.add(
                ids=data["ids"],
                documents=data["documents"],
                metadatas=data["metadatas"],
                embeddings=data.get("embeddings"),
            )
        return self.get_collection_info(new_name)

    def add_documents(self, collection_name: str, embeddings: List[List[float]], documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        col = self._get_collection(collection_name)
        col.add(embeddings=embeddings, documents=documents, metadatas=metadatas, ids=ids)

    def delete_document(self, collection_name: str, doc_id: str):
        col = self._get_collection(collection_name)
        before = col.count()
        col.delete(where={"doc_id": doc_id})
        after = col.count()
        return max(before - after, 0)

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
