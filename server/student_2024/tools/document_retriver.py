import chromadb
import os
from pathlib import Path

from dotenv import load_dotenv
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore


CHROMA_PATH = "student_db_2024"
COLLECTION_NAME = "rag_demo"
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


# Keep embeddings consistent with ingestion
Settings.embed_model = HuggingFaceEmbedding(model_name=_resolve_embedding_model())
Settings.llm = None  # plug in a local LLM here if available


def load_index() -> VectorStoreIndex:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)
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
    index = load_index()
    query_engine = build_query_engine(index)
    response = await query_engine.aquery(question)
    return str(response)
