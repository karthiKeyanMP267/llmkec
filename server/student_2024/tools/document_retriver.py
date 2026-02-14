import chromadb
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore


CHROMA_PATH = "student_db_2024"
COLLECTION_NAME = "rag_demo"
EMBED_MODEL = "BAAI/bge-base-en-v1.5"
SIMILARITY_TOP_K = 10
MMR_THRESHOLD = 0.5
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANK_TOP_N = 5


# Keep embeddings consistent with ingestion
Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
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

    reranker = SentenceTransformerRerank(
        model=RERANK_MODEL,
        top_n=RERANK_TOP_N,
    )

    return retriever, reranker


def build_query_engine(index: VectorStoreIndex):
    retriever, reranker = build_retriever(index)
    return RetrieverQueryEngine.from_args(
        retriever=retriever,
        node_postprocessors=[reranker],
    )


async def query_rag(question: str) -> str:
    index = load_index()
    query_engine = build_query_engine(index)
    response = await query_engine.aquery(question)
    return str(response)
