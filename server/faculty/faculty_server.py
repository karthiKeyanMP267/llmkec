"""
Faculty MCP Server - Query-only ChromaDB server for faculty data.

Exposes read-only tools via FastMCP (SSE transport).
All write/ingestion operations are restricted to the Admin Ingestion API.

Usage:
    python faculty_server.py [--data-dir ./faculty_db] [--mcp-port 3001]
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional

import chromadb
from dotenv import load_dotenv
from fastmcp import FastMCP
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("faculty_server")

# ---------------------------------------------------------------------------
# Embedding model configuration
# ---------------------------------------------------------------------------
_ALIAS_MAP = {
    "bge-large-en-v1.5": "BAAI/bge-large-en-v1.5",
    "e5-large-v2": "intfloat/e5-large-v2",
    "gte-large": "thenlper/gte-large",
    "bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
    "e5-base-v2": "intfloat/e5-base-v2",
    "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
}

_embedding_model: Optional[SentenceTransformer] = None


def _resolve_model_name() -> str:
    env_path = Path(__file__).resolve().parent / ".env.ingestion"
    if env_path.exists():
        load_dotenv(env_path, override=False)
    raw = os.getenv("EMBEDDING_MODEL", "bge-base-en-v1.5")
    return _ALIAS_MAP.get(raw, raw)


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        model_name = _resolve_model_name()
        logger.info("Loading embedding model: %s", model_name)
        _embedding_model = SentenceTransformer(model_name)
        dim = _embedding_model.get_sentence_embedding_dimension()
        logger.info("Embedding model loaded (dim=%d)", dim)
    return _embedding_model


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = get_embedding_model()
    vectors = model.encode(texts, show_progress_bar=False)
    return vectors.tolist()


# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("faculty-query")

# ---------------------------------------------------------------------------
# ChromaDB client (global singleton)
# ---------------------------------------------------------------------------
_chroma_client: Optional[chromadb.ClientAPI] = None


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Faculty Query MCP Server")
    parser.add_argument("--data-dir", default=os.getenv("CHROMA_DATA_DIR", "./faculty_db"),
                        help="Path to ChromaDB persistent storage (default: ./faculty_db)")
    parser.add_argument("--mcp-host", default=os.getenv("MCP_HOST", "localhost"),
                        help="Host for the MCP SSE server (default: localhost)")
    parser.add_argument("--mcp-port", type=int, default=int(os.getenv("MCP_PORT", "3001")),
                        help="Port for the MCP SSE server (default: 3001)")
    parser.add_argument("--transport", choices=["stdio", "sse"], default=os.getenv("MCP_TRANSPORT", "sse"),
                        help="Transport type (default: sse)")
    return parser


def get_chroma_client(args=None) -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        if args is None:
            args = create_parser().parse_args()
        data_dir = args.data_dir
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        logger.info("Initializing ChromaDB at: %s", data_dir)
        _chroma_client = chromadb.PersistentClient(path=data_dir)
        logger.info("ChromaDB client ready")
    return _chroma_client


# ---------------------------------------------------------------------------
# QUERY-ONLY TOOLS  (no add / update / delete / create / fork / reset)
# ---------------------------------------------------------------------------

@mcp.tool()
async def chroma_list_collections(limit: int = 100, offset: int = 0) -> List[Dict]:
    """List all collections in the faculty ChromaDB."""
    client = get_chroma_client()
    try:
        collections = client.list_collections(limit=limit, offset=offset)
        result = []
        for col in collections:
            try:
                count = col.count()
            except Exception:
                count = -1
            result.append({"name": col.name, "count": count})
        return result if result else [{"name": "__NO_COLLECTIONS__", "count": 0}]
    except Exception as exc:
        logger.exception("Failed to list collections")
        raise RuntimeError(f"Failed to list collections: {exc}") from exc


@mcp.tool()
async def chroma_get_collection_info(collection_name: str) -> Dict:
    """Get metadata and sample documents from a collection."""
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        count = collection.count()
        sample = collection.peek(limit=3)
        return {
            "name": collection_name,
            "count": count,
            "metadata": collection.metadata or {},
            "sample_documents": sample,
        }
    except Exception as exc:
        logger.exception("Failed to get collection info for '%s'", collection_name)
        raise RuntimeError(f"Collection '{collection_name}' not found or inaccessible: {exc}") from exc


@mcp.tool()
async def chroma_get_collection_count(collection_name: str) -> int:
    """Return the number of documents in a collection."""
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        return collection.count()
    except Exception as exc:
        logger.exception("Failed to count collection '%s'", collection_name)
        raise RuntimeError(f"Collection '{collection_name}' not found: {exc}") from exc


@mcp.tool()
async def chroma_query_documents(
    collection_name: str,
    query_texts: List[str],
    n_results: int = 5,
    where: Optional[Dict] = None,
    where_document: Optional[Dict] = None,
    include: List[str] = ["documents", "metadatas", "distances"],
) -> Dict:
    """Query a collection using semantic search with the correct embedding model.

    This tool embeds the query with the SAME model used during ingestion
    (bge-base-en-v1.5, 768-dim) to avoid dimension mismatches.
    """
    if not query_texts:
        raise ValueError("query_texts must not be empty")

    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
    except Exception as exc:
        raise RuntimeError(f"Collection '{collection_name}' not found: {exc}") from exc

    query_embeddings = embed_texts(query_texts)

    try:
        return collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=include,
        )
    except Exception as exc:
        logger.exception("Query failed on collection '%s'", collection_name)
        raise RuntimeError(f"Failed to query '{collection_name}': {exc}") from exc


@mcp.tool()
async def chroma_get_documents(
    collection_name: str,
    ids: Optional[List[str]] = None,
    where: Optional[Dict] = None,
    where_document: Optional[Dict] = None,
    include: List[str] = ["documents", "metadatas"],
    limit: int = 20,
    offset: int = 0,
) -> Dict:
    """Retrieve documents from a collection by ID or filter (no embedding needed)."""
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        return collection.get(
            ids=ids,
            where=where,
            where_document=where_document,
            include=include,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        logger.exception("Failed to get documents from '%s'", collection_name)
        raise RuntimeError(f"Failed to get documents from '{collection_name}': {exc}") from exc


@mcp.tool()
async def chroma_peek_collection(collection_name: str, limit: int = 5) -> Dict:
    """Peek at a few documents in a collection (quick preview)."""
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        return collection.peek(limit=limit)
    except Exception as exc:
        logger.exception("Failed to peek collection '%s'", collection_name)
        raise RuntimeError(f"Failed to peek '{collection_name}': {exc}") from exc


@mcp.tool()
async def chroma_search_by_text(
    collection_name: str,
    query_text: str,
    n_results: int = 10,
    where: Optional[Dict] = None,
    max_distance: Optional[float] = None,
) -> Dict:
    """Search a collection by text with optional distance filtering.

    Uses the correct embedding model to avoid dimension mismatches.
    """
    if not query_text or not query_text.strip():
        raise ValueError("query_text must not be empty")

    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
    except Exception as exc:
        raise RuntimeError(f"Collection '{collection_name}' not found: {exc}") from exc

    query_embedding = embed_texts([query_text])

    try:
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.exception("Search failed on '%s'", collection_name)
        raise RuntimeError(f"Search failed on '{collection_name}': {exc}") from exc

    if max_distance is not None and results.get("distances"):
        filtered = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        for i, dist in enumerate(results["distances"][0]):
            if dist <= max_distance:
                filtered["ids"][0].append(results["ids"][0][i])
                filtered["documents"][0].append(results["documents"][0][i])
                filtered["metadatas"][0].append(results["metadatas"][0][i])
                filtered["distances"][0].append(dist)
        return filtered

    return results


@mcp.tool()
async def chroma_count_documents_with_filter(
    collection_name: str,
    where: Optional[Dict] = None,
    where_document: Optional[Dict] = None,
) -> int:
    """Count documents matching specific metadata or content filters."""
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        results = collection.get(
            where=where,
            where_document=where_document,
            include=[],
        )
        return len(results["ids"])
    except Exception as exc:
        logger.exception("Failed to count filtered documents in '%s'", collection_name)
        raise RuntimeError(f"Count failed on '{collection_name}': {exc}") from exc


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = create_parser()
    args = parser.parse_args()

    env_path = Path(__file__).resolve().parent / ".env.ingestion"
    if env_path.exists():
        load_dotenv(env_path, override=False)

    try:
        get_chroma_client(args)
        logger.info("ChromaDB client initialised")
    except Exception as exc:
        logger.critical("Cannot start - ChromaDB init failed: %s", exc)
        sys.exit(1)

    try:
        get_embedding_model()
        logger.info("Embedding model ready")
    except Exception as exc:
        logger.critical("Cannot start - Embedding model load failed: %s", exc)
        sys.exit(1)

    logger.info(
        "Starting Faculty MCP server (transport=%s, host=%s, port=%d)",
        args.transport, args.mcp_host, args.mcp_port,
    )

    mcp.run(transport=args.transport, host=args.mcp_host, port=args.mcp_port)


if __name__ == "__main__":
    main()
