"""
Chroma MCP Server - Official chroma-mcp compatible server
Based on: https://github.com/chroma-core/chroma-mcp

Simplified for persistent client usage with your local faculty_db folder.

Usage:
    python mcp_chroma_server.py --client-type persistent --data-dir ./faculty_db

For Claude Desktop, add to config:
{
  "mcpServers": {
    "chroma": {
      "command": "python",
      "args": [
        "C:/Users/vikym/Documents/GitHub/llmAgent/chromaDB_MCP/mcp_chroma_server.py",
        "--client-type", "persistent",
        "--data-dir", "C:/Users/vikym/Documents/GitHub/llmAgent/chromaDB_MCP/faculty_db"
      ]
    }
  }
}
"""

from typing import Dict, List
import chromadb
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from fastmcp import FastMCP
from chromadb.config import Settings
from chromadb.api.collection_configuration import CreateCollectionConfiguration
from chromadb.api import EmbeddingFunction
from chromadb.utils.embedding_functions import (
    DefaultEmbeddingFunction,
    CohereEmbeddingFunction,
    OpenAIEmbeddingFunction,
    JinaEmbeddingFunction,
    VoyageAIEmbeddingFunction,
    RoboflowEmbeddingFunction,
)

# Initialize FastMCP server
mcp = FastMCP("chroma")

# Global ChromaDB client
_chroma_client = None

# Known embedding functions
mcp_known_embedding_functions: Dict[str, EmbeddingFunction] = {
    "default": DefaultEmbeddingFunction,
    "cohere": CohereEmbeddingFunction,
    "openai": OpenAIEmbeddingFunction,
    "jina": JinaEmbeddingFunction,
    "voyageai": VoyageAIEmbeddingFunction,
    "roboflow": RoboflowEmbeddingFunction,
}


def create_parser():
    """Create and return the argument parser."""
    parser = argparse.ArgumentParser(description='FastMCP server for Chroma DB')
    parser.add_argument('--client-type', 
                       choices=['http', 'cloud', 'persistent', 'ephemeral'],
                       default=os.getenv('CHROMA_CLIENT_TYPE', 'persistent'),
                       help='Type of Chroma client to use (default: persistent)')
    parser.add_argument('--data-dir',
                       default=os.getenv('CHROMA_DATA_DIR', './faculty_db'),
                       help='Directory for persistent client data')
    parser.add_argument('--host', 
                       help='Chroma host (required for http client)', 
                       default=os.getenv('CHROMA_HOST'))
    parser.add_argument('--port', 
                       help='Chroma port (optional for http client)', 
                       default=os.getenv('CHROMA_PORT'))
    parser.add_argument('--custom-auth-credentials',
                       help='Custom auth credentials (optional for http client)', 
                       default=os.getenv('CHROMA_CUSTOM_AUTH_CREDENTIALS'))
    parser.add_argument('--tenant', 
                       help='Chroma tenant (optional for http client)', 
                       default=os.getenv('CHROMA_TENANT'))
    parser.add_argument('--database', 
                       help='Chroma database (required if tenant is provided)', 
                       default=os.getenv('CHROMA_DATABASE'))
    parser.add_argument('--api-key', 
                       help='Chroma API key (required if tenant is provided)', 
                       default=os.getenv('CHROMA_API_KEY'))
    parser.add_argument('--ssl', 
                       help='Use SSL (optional for http client)', 
                       type=lambda x: x.lower() in ['true', 'yes', '1', 't', 'y'],
                       default=os.getenv('CHROMA_SSL', 'true').lower() in ['true', 'yes', '1', 't', 'y'])
    parser.add_argument('--dotenv-path', 
                       help='Path to .env file', 
                       default=os.getenv('CHROMA_DOTENV_PATH', '.chroma_env'))
    
    # MCP Server transport arguments
    parser.add_argument('--mcp-host', 
                       help='Host for MCP HTTP server', 
                       default=os.getenv('MCP_HOST', 'localhost'))
    parser.add_argument('--mcp-port', 
                       help='Port for MCP HTTP server', 
                       type=int,
                       default=int(os.getenv('MCP_PORT', '3001')))
    parser.add_argument('--transport', 
                       choices=['stdio', 'http', 'sse'],
                       default=os.getenv('MCP_TRANSPORT', 'sse'),
                       help='Transport type for MCP server (default: sse)')
    return parser


def get_chroma_client(args=None):
    """Get or create the global Chroma client instance."""
    global _chroma_client
    if _chroma_client is None:
        if args is None:
            # Create parser and parse args if not provided
            parser = create_parser()
            args = parser.parse_args()
        
        # Load environment variables from .env file if it exists
        load_dotenv(dotenv_path=args.dotenv_path)
        
        if args.client_type == 'http':
            if not args.host:
                raise ValueError("Host must be provided via --host flag or CHROMA_HOST environment variable when using HTTP client")
            
            settings = Settings()
            if args.custom_auth_credentials:
                settings = Settings(
                    chroma_client_auth_provider="chromadb.auth.basic_authn.BasicAuthClientProvider",
                    chroma_client_auth_credentials=args.custom_auth_credentials
                )
            
            _chroma_client = chromadb.HttpClient(
                host=args.host,
                port=args.port if args.port else None,
                ssl=args.ssl,
                settings=settings
            )
            
        elif args.client_type == 'cloud':
            if not args.tenant:
                raise ValueError("Tenant must be provided via --tenant flag or CHROMA_TENANT environment variable when using cloud client")
            if not args.database:
                raise ValueError("Database must be provided via --database flag or CHROMA_DATABASE environment variable when using cloud client")
            if not args.api_key:
                raise ValueError("API key must be provided via --api-key flag or CHROMA_API_KEY environment variable when using cloud client")
            
            _chroma_client = chromadb.HttpClient(
                host="api.trychroma.com",
                ssl=True,
                tenant=args.tenant,
                database=args.database,
                headers={'x-chroma-token': args.api_key}
            )
                
        elif args.client_type == 'persistent':
            if not args.data_dir:
                raise ValueError("Data directory must be provided via --data-dir flag when using persistent client")
            
            # Ensure directory exists
            Path(args.data_dir).mkdir(parents=True, exist_ok=True)
            print(f"Initializing ChromaDB with persistent storage at: {args.data_dir}", file=sys.stderr)
            _chroma_client = chromadb.PersistentClient(path=args.data_dir)
            
        else:  # ephemeral
            print("Initializing ChromaDB with ephemeral storage", file=sys.stderr)
            _chroma_client = chromadb.EphemeralClient()
            
    return _chroma_client


##### Collection Management Tools #####

@mcp.tool()
async def chroma_list_collections(
    limit: int | None = None,
    offset: int | None = None
) -> List[str]:
    """List all collection names in the Chroma database with pagination support.
    
    Args:
        limit: Optional maximum number of collections to return
        offset: Optional number of collections to skip before returning results
    
    Returns:
        List of collection names or ["__NO_COLLECTIONS_FOUND__"] if database is empty
    """
    client = get_chroma_client()
    try:
        colls = client.list_collections(limit=limit, offset=offset)
        if not colls:
            return ["__NO_COLLECTIONS_FOUND__"]
        return [coll.name for coll in colls]
    except Exception as e:
        raise Exception(f"Failed to list collections: {str(e)}") from e


@mcp.tool()
async def chroma_create_collection(
    collection_name: str,
    embedding_function_name: str = "default",
    metadata: Dict | None = None,
) -> str:
    """Create a new Chroma collection with configurable embedding functions.
    
    Args:
        collection_name: Name of the collection to create
        embedding_function_name: Name of the embedding function to use. Options: 'default', 'cohere', 'openai', 'jina', 'voyageai', 'roboflow'
        metadata: Optional metadata dict to add to the collection
    
    Returns:
        Success message
    """
    client = get_chroma_client()
    
    embedding_function = mcp_known_embedding_functions.get(embedding_function_name)
    if not embedding_function:
        raise ValueError(f"Unknown embedding function: {embedding_function_name}. Valid options: {list(mcp_known_embedding_functions.keys())}")
    
    configuration = CreateCollectionConfiguration(
        embedding_function=embedding_function()
    )
    
    try:
        client.create_collection(
            name=collection_name,
            configuration=configuration,
            metadata=metadata
        )
        return f"Successfully created collection '{collection_name}' with {embedding_function_name} embedding function"
    except Exception as e:
        raise Exception(f"Failed to create collection '{collection_name}': {str(e)}") from e


@mcp.tool()
async def chroma_get_collection_info(collection_name: str) -> Dict:
    """Get information about a Chroma collection.
    
    Args:
        collection_name: Name of the collection to get info about
    
    Returns:
        Dictionary with collection info including count and sample documents
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        count = collection.count()
        peek_results = collection.peek(limit=3)
        
        return {
            "name": collection_name,
            "count": count,
            "sample_documents": peek_results
        }
    except Exception as e:
        raise Exception(f"Failed to get collection info for '{collection_name}': {str(e)}") from e


@mcp.tool()
async def chroma_get_collection_count(collection_name: str) -> int:
    """Get the number of documents in a Chroma collection.
    
    Args:
        collection_name: Name of the collection to count
    
    Returns:
        Number of documents in the collection
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        return collection.count()
    except Exception as e:
        raise Exception(f"Failed to get collection count for '{collection_name}': {str(e)}") from e


@mcp.tool()
async def chroma_modify_collection(
    collection_name: str,
    new_name: str | None = None,
    new_metadata: Dict | None = None,
) -> str:
    """Modify a Chroma collection's name or metadata.
    
    Args:
        collection_name: Name of the collection to modify
        new_name: Optional new name for the collection
        new_metadata: Optional new metadata for the collection
    
    Returns:
        Success message
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        collection.modify(name=new_name, metadata=new_metadata)
        
        modified_aspects = []
        if new_name:
            modified_aspects.append("name")
        if new_metadata:
            modified_aspects.append("metadata")
        
        return f"Successfully modified collection {collection_name}: updated {' and '.join(modified_aspects)}"
    except Exception as e:
        raise Exception(f"Failed to modify collection '{collection_name}': {str(e)}") from e


@mcp.tool()
async def chroma_fork_collection(
    collection_name: str,
    new_collection_name: str,
) -> str:
    """Fork a Chroma collection.
    
    Args:
        collection_name: Name of the collection to fork
        new_collection_name: Name of the new collection to create
    
    Returns:
        Success message
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        collection.fork(new_collection_name)
        return f"Successfully forked collection {collection_name} to {new_collection_name}"
    except Exception as e:
        raise Exception(f"Failed to fork collection '{collection_name}': {str(e)}") from e


@mcp.tool()
async def chroma_delete_collection(collection_name: str) -> str:
    """Delete a Chroma collection.
    
    Args:
        collection_name: Name of the collection to delete
    
    Returns:
        Success message
    """
    client = get_chroma_client()
    try:
        client.delete_collection(collection_name)
        return f"Successfully deleted collection '{collection_name}'"
    except Exception as e:
        raise Exception(f"Failed to delete collection '{collection_name}': {str(e)}") from e


##### Document Operations #####

@mcp.tool()
async def chroma_add_documents(
    collection_name: str,
    documents: List[str],
    ids: List[str],
    metadatas: List[Dict] | None = None
) -> str:
    """Add documents to a Chroma collection.
    
    Args:
        collection_name: Name of the collection to add documents to
        documents: List of text documents to add
        ids: List of IDs for the documents (required)
        metadatas: Optional list of metadata dictionaries for each document
    
    Returns:
        Success message
    """
    if not documents:
        raise ValueError("The 'documents' list cannot be empty.")
    
    if not ids:
        raise ValueError("The 'ids' list is required and cannot be empty.")
    
    if any(not id.strip() for id in ids):
        raise ValueError("IDs cannot be empty strings.")
    
    if len(ids) != len(documents):
        raise ValueError(f"Number of ids ({len(ids)}) must match number of documents ({len(documents)}).")
    
    client = get_chroma_client()
    try:
        collection = client.get_or_create_collection(collection_name)
        
        # Check for duplicate IDs
        existing_ids = collection.get(include=[])["ids"]
        duplicate_ids = [id for id in ids if id in existing_ids]
        
        if duplicate_ids:
            raise ValueError(
                f"The following IDs already exist in collection '{collection_name}': {duplicate_ids}. "
                f"Use 'chroma_update_documents' to update existing documents."
            )
        
        result = collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        return f"Successfully added {len(documents)} documents to collection {collection_name}"
    except Exception as e:
        raise Exception(f"Failed to add documents to collection '{collection_name}': {str(e)}") from e


@mcp.tool()
async def chroma_query_documents(
    collection_name: str,
    query_texts: List[str],
    n_results: int = 5,
    where: Dict | None = None,
    where_document: Dict | None = None,
    include: List[str] = ["documents", "metadatas", "distances"]
) -> Dict:
    """Query documents from a Chroma collection with advanced filtering.
    
    Args:
        collection_name: Name of the collection to query
        query_texts: List of query texts to search for
        n_results: Number of results to return per query
        where: Optional metadata filters using Chroma's query operators
        where_document: Optional document content filters
        include: List of what to include in response. By default, this will include documents, metadatas, and distances.
    
    Returns:
        Dictionary with query results including documents, metadatas, and distances
    """
    if not query_texts:
        raise ValueError("The 'query_texts' list cannot be empty.")
    
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        return collection.query(
            query_texts=query_texts,
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=include
        )
    except Exception as e:
        raise Exception(f"Failed to query documents from '{collection_name}': {str(e)}") from e


@mcp.tool()
async def chroma_get_documents(
    collection_name: str,
    ids: List[str] | None = None,
    where: Dict | None = None,
    where_document: Dict | None = None,
    include: List[str] = ["documents", "metadatas"],
    limit: int | None = None,
    offset: int | None = None
) -> Dict:
    """Get documents from a Chroma collection with optional filtering.
    
    Args:
        collection_name: Name of the collection to get documents from
        ids: Optional list of document IDs to retrieve
        where: Optional metadata filters using Chroma's query operators
        where_document: Optional document content filters
        include: List of what to include in response. By default, this will include documents, and metadatas.
        limit: Optional maximum number of documents to return
        offset: Optional number of documents to skip before returning results
    
    Returns:
        Dictionary containing the matching documents, their IDs, and requested includes
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        return collection.get(
            ids=ids,
            where=where,
            where_document=where_document,
            include=include,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        raise Exception(f"Failed to get documents from '{collection_name}': {str(e)}") from e


@mcp.tool()
async def chroma_update_documents(
    collection_name: str,
    ids: List[str],
    embeddings: List[List[float]] | None = None,
    metadatas: List[Dict] | None = None,
    documents: List[str] | None = None
) -> str:
    """Update documents in a Chroma collection.

    Args:
        collection_name: Name of the collection to update documents in
        ids: List of document IDs to update (required)
        embeddings: Optional list of new embeddings for the documents.
                    Must match length of ids if provided.
        metadatas: Optional list of new metadata dictionaries for the documents.
                   Must match length of ids if provided.
        documents: Optional list of new text documents.
                   Must match length of ids if provided.

    Returns:
        A confirmation message indicating the number of documents updated.
    """
    if not ids:
        raise ValueError("The 'ids' list cannot be empty.")

    if embeddings is None and metadatas is None and documents is None:
        raise ValueError(
            "At least one of 'embeddings', 'metadatas', or 'documents' "
            "must be provided for update."
        )

    # Ensure provided lists match the length of ids if they are not None
    if embeddings is not None and len(embeddings) != len(ids):
        raise ValueError("Length of 'embeddings' list must match length of 'ids' list.")
    if metadatas is not None and len(metadatas) != len(ids):
        raise ValueError("Length of 'metadatas' list must match length of 'ids' list.")
    if documents is not None and len(documents) != len(ids):
        raise ValueError("Length of 'documents' list must match length of 'ids' list.")

    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
    except Exception as e:
        raise Exception(
            f"Failed to get collection '{collection_name}': {str(e)}"
        ) from e

    # Prepare arguments for update, excluding None values at the top level
    update_args = {
        "ids": ids,
        "embeddings": embeddings,
        "metadatas": metadatas,
        "documents": documents,
    }
    kwargs = {k: v for k, v in update_args.items() if v is not None}

    try:
        collection.update(**kwargs)
        return (
            f"Successfully processed update request for {len(ids)} documents in "
            f"collection '{collection_name}'. Note: Non-existent IDs are ignored by ChromaDB."
        )
    except Exception as e:
        raise Exception(
            f"Failed to update documents in collection '{collection_name}': {str(e)}"
        ) from e


@mcp.tool()
async def chroma_delete_documents(
    collection_name: str,
    ids: List[str]
) -> str:
    """Delete documents from a Chroma collection.

    Args:
        collection_name: Name of the collection to delete documents from
        ids: List of document IDs to delete

    Returns:
        A confirmation message indicating the number of documents deleted.
    """
    if not ids:
        raise ValueError("The 'ids' list cannot be empty.")

    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
    except Exception as e:
        raise Exception(
            f"Failed to get collection '{collection_name}': {str(e)}"
        ) from e

    try:
        collection.delete(ids=ids)
        return (
            f"Successfully deleted {len(ids)} documents from "
            f"collection '{collection_name}'. Note: Non-existent IDs are ignored by ChromaDB."
        )
    except Exception as e:
        raise Exception(
            f"Failed to delete documents from collection '{collection_name}': {str(e)}"
        ) from e


##### Helper Tools #####

@mcp.tool()
async def chroma_peek_collection(
    collection_name: str,
    limit: int = 5
) -> Dict:
    """Peek at documents in a Chroma collection.
    
    Args:
        collection_name: Name of the collection to peek into
        limit: Number of documents to peek at (default: 5)
    
    Returns:
        Dictionary with sample documents
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        return collection.peek(limit=limit)
    except Exception as e:
        raise Exception(f"Failed to peek collection '{collection_name}': {str(e)}") from e


##### Advanced Operations for Scaling #####

@mcp.tool()
async def chroma_get_or_create_collection(
    collection_name: str,
    embedding_function_name: str = "default",
    metadata: Dict | None = None,
) -> str:
    """Get an existing collection or create it if it doesn't exist (idempotent operation).
    
    Args:
        collection_name: Name of the collection
        embedding_function_name: Name of the embedding function to use if creating
        metadata: Optional metadata dict for the collection
    
    Returns:
        Status message indicating if collection was created or already exists
    """
    client = get_chroma_client()
    
    try:
        collection = client.get_collection(collection_name)
        return f"Collection '{collection_name}' already exists with {collection.count()} documents"
    except:
        # Collection doesn't exist, create it
        embedding_function = mcp_known_embedding_functions.get(embedding_function_name)
        if not embedding_function:
            raise ValueError(f"Unknown embedding function: {embedding_function_name}")
        
        configuration = CreateCollectionConfiguration(
            embedding_function=embedding_function()
        )
        
        client.create_collection(
            name=collection_name,
            configuration=configuration,
            metadata=metadata
        )
        return f"Created new collection '{collection_name}' with {embedding_function_name} embedding function"


@mcp.tool()
async def chroma_upsert_documents(
    collection_name: str,
    documents: List[str],
    ids: List[str],
    metadatas: List[Dict] | None = None
) -> str:
    """Upsert documents (add if new, update if exists) - useful for incremental updates.
    
    Args:
        collection_name: Name of the collection
        documents: List of text documents
        ids: List of document IDs
        metadatas: Optional list of metadata dictionaries
    
    Returns:
        Success message
    """
    if not documents or not ids:
        raise ValueError("Both 'documents' and 'ids' are required")
    
    if len(ids) != len(documents):
        raise ValueError(f"Number of ids ({len(ids)}) must match documents ({len(documents)})")
    
    client = get_chroma_client()
    try:
        collection = client.get_or_create_collection(collection_name)
        
        collection.upsert(
            documents=documents,
            ids=ids,
            metadatas=metadatas
        )
        
        return f"Successfully upserted {len(documents)} documents in collection '{collection_name}'"
    except Exception as e:
        raise Exception(f"Failed to upsert documents: {str(e)}") from e


@mcp.tool()
async def chroma_count_documents_with_filter(
    collection_name: str,
    where: Dict | None = None,
    where_document: Dict | None = None
) -> int:
    """Count documents matching specific filters (useful for large collections).
    
    Args:
        collection_name: Name of the collection
        where: Optional metadata filters
        where_document: Optional document content filters
    
    Returns:
        Number of documents matching the filters
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        
        # Get filtered documents and count them
        results = collection.get(
            where=where,
            where_document=where_document,
            include=[]  # Don't include any data, just get IDs
        )
        
        return len(results["ids"])
    except Exception as e:
        raise Exception(f"Failed to count filtered documents: {str(e)}") from e


@mcp.tool()
async def chroma_delete_documents_by_filter(
    collection_name: str,
    where: Dict | None = None,
    where_document: Dict | None = None
) -> str:
    """Delete all documents matching filters (useful for bulk cleanup).
    
    Args:
        collection_name: Name of the collection
        where: Optional metadata filters
        where_document: Optional document content filters
    
    Returns:
        Success message with count of deleted documents
    """
    if not where and not where_document:
        raise ValueError("At least one filter (where or where_document) must be provided")
    
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        
        collection.delete(
            where=where,
            where_document=where_document
        )
        
        return f"Successfully deleted documents from collection '{collection_name}' matching the filters"
    except Exception as e:
        raise Exception(f"Failed to delete filtered documents: {str(e)}") from e


@mcp.tool()
async def chroma_batch_add_documents(
    collection_name: str,
    documents: List[str],
    ids: List[str],
    metadatas: List[Dict] | None = None,
    batch_size: int = 100
) -> str:
    """Add documents in batches for better performance with large datasets.
    
    Args:
        collection_name: Name of the collection
        documents: List of text documents
        ids: List of document IDs
        metadatas: Optional list of metadata dictionaries
        batch_size: Number of documents per batch (default: 100)
    
    Returns:
        Success message with batch statistics
    """
    if not documents or not ids:
        raise ValueError("Both 'documents' and 'ids' are required")
    
    if len(ids) != len(documents):
        raise ValueError(f"Number of ids must match number of documents")
    
    client = get_chroma_client()
    try:
        collection = client.get_or_create_collection(collection_name)
        
        total_docs = len(documents)
        batches = (total_docs + batch_size - 1) // batch_size
        
        for i in range(0, total_docs, batch_size):
            end_idx = min(i + batch_size, total_docs)
            batch_docs = documents[i:end_idx]
            batch_ids = ids[i:end_idx]
            batch_metas = metadatas[i:end_idx] if metadatas else None
            
            collection.add(
                documents=batch_docs,
                ids=batch_ids,
                metadatas=batch_metas
            )
        
        return f"Successfully added {total_docs} documents in {batches} batches to collection '{collection_name}'"
    except Exception as e:
        raise Exception(f"Failed to batch add documents: {str(e)}") from e


@mcp.tool()
async def chroma_reset_collection(
    collection_name: str
) -> str:
    """Delete all documents from a collection without deleting the collection itself.
    
    Args:
        collection_name: Name of the collection to reset
    
    Returns:
        Success message with count of deleted documents
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        
        # Get current count
        count_before = collection.count()
        
        # Get all IDs
        all_docs = collection.get(include=[])
        all_ids = all_docs["ids"]
        
        if all_ids:
            collection.delete(ids=all_ids)
        
        return f"Successfully reset collection '{collection_name}' - removed {count_before} documents"
    except Exception as e:
        raise Exception(f"Failed to reset collection '{collection_name}': {str(e)}") from e


@mcp.tool()
async def chroma_get_collection_metadata(
    collection_name: str
) -> Dict:
    """Get detailed metadata about a collection (useful for monitoring).
    
    Args:
        collection_name: Name of the collection
    
    Returns:
        Dictionary with collection metadata
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        
        return {
            "name": collection_name,
            "count": collection.count(),
            "metadata": collection.metadata if hasattr(collection, 'metadata') else {}
        }
    except Exception as e:
        raise Exception(f"Failed to get collection metadata: {str(e)}") from e


@mcp.tool()
async def chroma_search_by_text_with_limit(
    collection_name: str,
    query_text: str,
    n_results: int = 10,
    where: Dict | None = None,
    min_distance: float | None = None,
    max_distance: float | None = None
) -> Dict:
    """Advanced search with distance filtering (useful for quality control).
    
    Args:
        collection_name: Name of the collection to query
        query_text: Text to search for
        n_results: Number of results to return
        where: Optional metadata filters
        min_distance: Minimum distance threshold (exclude too similar results)
        max_distance: Maximum distance threshold (exclude dissimilar results)
    
    Returns:
        Filtered query results
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        
        # Apply distance filtering if specified
        if min_distance is not None or max_distance is not None:
            filtered_results = {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }
            
            for i, distance in enumerate(results["distances"][0]):
                if (min_distance is None or distance >= min_distance) and \
                   (max_distance is None or distance <= max_distance):
                    filtered_results["ids"][0].append(results["ids"][0][i])
                    filtered_results["documents"][0].append(results["documents"][0][i])
                    filtered_results["metadatas"][0].append(results["metadatas"][0][i])
                    filtered_results["distances"][0].append(distance)
            
            return filtered_results
        
        return results
    except Exception as e:
        raise Exception(f"Failed to search with distance filtering: {str(e)}") from e


def main():
    """Entry point for the Chroma MCP server."""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.dotenv_path:
        load_dotenv(dotenv_path=args.dotenv_path)
        # re-parse args to read the updated environment variables
        parser = create_parser()
        args = parser.parse_args()
    
    # Validate required arguments based on client type
    if args.client_type == 'http':
        if not args.host:
            parser.error("Host must be provided via --host flag or CHROMA_HOST environment variable when using HTTP client")
    
    elif args.client_type == 'cloud':
        if not args.tenant:
            parser.error("Tenant must be provided via --tenant flag or CHROMA_TENANT environment variable when using cloud client")
        if not args.database:
            parser.error("Database must be provided via --database flag or CHROMA_DATABASE environment variable when using cloud client")
        if not args.api_key:
            parser.error("API key must be provided via --api-key flag or CHROMA_API_KEY environment variable when using cloud client")
    
    # Initialize client with parsed args
    try:
        get_chroma_client(args)
        print("Successfully initialized Chroma client", file=sys.stderr)
    except Exception as e:
        print(f"Failed to initialize Chroma client: {str(e)}", file=sys.stderr)
        sys.exit(1)
    
    # Run the MCP server 
    print("Starting FastMCP server", file=sys.stderr)
    print(f"Transport: {args.transport}", file=sys.stderr)
    print(f"Running on {args.mcp_host}:{args.mcp_port}", file=sys.stderr)
    
    # Run with transport, host, and port
    mcp.run(transport=args.transport, host=args.mcp_host, port=args.mcp_port)


if __name__ == "__main__":
    main()
