import chromadb
import logging
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


CHROMA_PATH = str(Path(__file__).resolve().parents[1] / "student_db_2024")
SIMILARITY_TOP_K = 10
MMR_THRESHOLD = 0.5


def _resolve_embedding_model() -> str:
    env_path = Path(__file__).resolve().parents[1] / ".env.ingestion"
    load_dotenv(env_path, override=False)
    value = os.getenv("EMBEDDING_MODEL", "bge-base-en-v1.5")
    alias_map = {
        "bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
        "e5-large-v2": "intfloat/e5-large-v2",
        "gte-large": "thenlper/gte-large",
        "bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
        "e5-base-v2": "intfloat/e5-base-v2",
        "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
    }
    return alias_map.get(value, value)


def _resolve_collection_names(client: chromadb.PersistentClient) -> List[str]:
    env_path = Path(__file__).resolve().parents[1] / ".env.ingestion"
    load_dotenv(env_path, override=False)

    available = [c.name for c in client.list_collections()]
    available_set = set(available)

    requested_many = (os.getenv("STUDENT_COLLECTIONS") or "").strip()
    if requested_many:
        requested = [name.strip() for name in requested_many.split(",") if name.strip()]
        missing = [name for name in requested if name not in available_set]
        if missing:
            logger.error(
                "Configured collections not found: %s. Available collections: %s",
                ', '.join(missing), ', '.join(available) or 'none'
            )
            return []
        return requested

    requested_single = (os.getenv("STUDENT_COLLECTION") or os.getenv("COLLECTION_NAME") or "").strip()
    if requested_single:
        if requested_single in available_set:
            return [requested_single]
        logger.error(
            "Configured collection '%s' not found. Available collections: %s",
            requested_single, ', '.join(available) or 'none'
        )
        return []

    default_candidates = [name for name in ("student_data_2024", "student_data_2022", "rag_demo") if name in available_set]
    if default_candidates:
        return default_candidates

    logger.error("No supported collection found. Available collections: %s", ', '.join(available) or 'none')
    return []


# Keep embeddings consistent with ingestion
Settings.embed_model = HuggingFaceEmbedding(model_name=_resolve_embedding_model())
Settings.llm = None  # plug in a local LLM here if available


def load_index(collection_name: str) -> VectorStoreIndex:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(collection_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    return VectorStoreIndex.from_vector_store(vector_store)


def build_retriever(index: VectorStoreIndex):
    retriever = index.as_retriever(
        similarity_top_k=SIMILARITY_TOP_K,
        vector_store_query_mode="mmr",
        vector_store_kwargs={"mmr_threshold": MMR_THRESHOLD},
    )
    return retriever


def build_query_engine(index: VectorStoreIndex):
    retriever = build_retriever(index)
    return RetrieverQueryEngine.from_args(
        retriever=retriever,
    )


async def query_rag(question: str) -> str:
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection_names = _resolve_collection_names(client)

        outputs: List[str] = []
        for collection_name in collection_names:
            index = load_index(collection_name)
            query_engine = build_query_engine(index)
            response = await query_engine.aquery(question)
            text = str(response).strip()
            if not text:
                continue
            outputs.append(f"[{collection_name}]\n{text}")

        if not outputs:
            return "No relevant content found in configured student collections."

        return "\n\n".join(outputs)
    except Exception as e:
        logger.error("query_rag failed: %s", e)
        return f"Error: Failed to query student regulations: {str(e)}"
