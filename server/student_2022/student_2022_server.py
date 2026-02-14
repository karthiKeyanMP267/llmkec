"""
Full-Featured Chroma MCP Server for KEC Syllabi Database
Runs with HTTP/SSE transport on port 8000 (configurable via env vars)

Usage:
        python mcp_server.py

Environment overrides:
        MCP_HOST (default: localhost)
        MCP_PORT (default: 8000)
        MCP_TRANSPORT (http or sse; default: http)

Access at: http://localhost:8000

For Claude Desktop config:
{
    "mcpServers": {
        "kec_syllabi": {
            "command": "python",
            "args": [
                "C:/Users/vikym/Documents/GitHub/llmAgent/llamaindex_2022/mcp_server.py"
            ]
        }
    }
}
"""

import os
from typing import Dict, List
import chromadb
import sys
from pathlib import Path
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("kec-syllabi-server")

BASE_DIR = Path(__file__).resolve().parent

# Configuration with env overrides; defaults to local repo paths
CHROMA_DATA_DIR = os.getenv("CHROMA_DATA_DIR", str(BASE_DIR / "student_db_2022"))
DEFAULT_COLLECTION = "kec_syllabi_regulations_r2022"
MCP_HOST = os.getenv("MCP_HOST", "localhost")

try:
    MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
except ValueError:
    MCP_PORT = 8000

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http")

# Global ChromaDB client
_chroma_client = None


def get_chroma_client():
    """Get or create the global Chroma client instance."""
    global _chroma_client
    if _chroma_client is None:
        data_path = Path(CHROMA_DATA_DIR)
        if not data_path.exists():
            raise ValueError(f"ChromaDB data directory not found: {CHROMA_DATA_DIR}")
        
        print(f"Initializing ChromaDB from: {CHROMA_DATA_DIR}", file=sys.stderr)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DATA_DIR)
        
        # Verify collection exists
        try:
            collection = _chroma_client.get_collection(DEFAULT_COLLECTION)
            print(f"✓ Found collection: {DEFAULT_COLLECTION} ({collection.count()} chunks)", file=sys.stderr)
        except Exception as e:
            print(f"⚠ Warning: Collection '{DEFAULT_COLLECTION}' not found", file=sys.stderr)
    
    return _chroma_client


##### Core Tools #####

@mcp.tool()
async def list_collections() -> List[str]:
    """List all available collections in the ChromaDB database.
    
    Returns:
        List of collection names
    """
    client = get_chroma_client()
    try:
        collections = client.list_collections()
        if not collections:
            return ["No collections found"]
        return [coll.name for coll in collections]
    except Exception as e:
        raise Exception(f"Failed to list collections: {str(e)}") from e


@mcp.tool()
async def get_collection_info(collection_name: str = DEFAULT_COLLECTION) -> Dict:
    """Get information about a collection.
    
    Args:
        collection_name: Name of the collection (default: kec_syllabi_regulations_r2022)
    
    Returns:
        Dictionary with collection info including document count and sample data
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        count = collection.count()
        
        # Get sample documents
        sample = collection.peek(limit=3)
        
        return {
            "name": collection_name,
            "total_documents": count,
            "sample_ids": sample.get("ids", [])[:3],
            "sample_metadata": sample.get("metadatas", [])[:3]
        }
    except Exception as e:
        raise Exception(f"Failed to get collection info: {str(e)}") from e


@mcp.tool()
async def query_syllabi(
    query: str,
    collection_name: str = DEFAULT_COLLECTION,
    n_results: int = 5,
    filter_department: str | None = None,
    filter_level: str | None = None,
    filter_program: str | None = None
) -> Dict:
    """Query the KEC syllabi and regulations database.
    
    Args:
        query: Search query text
        collection_name: Collection to query (default: kec_syllabi_regulations_r2022)
        n_results: Number of results to return (default: 5)
        filter_department: Optional filter by department (e.g., "CSE", "ECE", "AIML")
        filter_level: Optional filter by level ("UG" or "PG")
        filter_program: Optional filter by program type (e.g., "BE", "BTECH", "MBA")
    
    Returns:
        Dictionary with query results including documents, metadata, and distances
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        
        # Build metadata filter
        where_filter = {}
        if filter_department:
            where_filter["department"] = filter_department
        if filter_level:
            where_filter["level"] = filter_level
        if filter_program:
            where_filter["program_type"] = filter_program
        
        # Query
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter if where_filter else None,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format response
        formatted_results = []
        if results and results["documents"] and len(results["documents"]) > 0:
            for i in range(len(results["documents"][0])):
                formatted_results.append({
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                    "source_file": results["metadatas"][0][i].get("source_file", "Unknown"),
                    "department": results["metadatas"][0][i].get("department", "N/A"),
                    "level": results["metadatas"][0][i].get("level", "N/A"),
                    "program_type": results["metadatas"][0][i].get("program_type", "N/A")
                })
        
        return {
            "query": query,
            "total_results": len(formatted_results),
            "results": formatted_results
        }
    except Exception as e:
        raise Exception(f"Failed to query syllabi: {str(e)}") from e


@mcp.tool()
async def search_by_department(
    department: str,
    query: str = "",
    n_results: int = 10
) -> Dict:
    """Search syllabi for a specific department.
    
    Args:
        department: Department code (e.g., "CSE", "ECE", "AIML", "MBA")
        query: Optional search query (if empty, returns all documents from department)
        n_results: Number of results to return
    
    Returns:
        Dictionary with search results from the specified department
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(DEFAULT_COLLECTION)
        
        if query:
            # Query with department filter
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"department": department},
                include=["documents", "metadatas", "distances"]
            )
            
            formatted_results = []
            if results and results["documents"] and len(results["documents"]) > 0:
                for i in range(len(results["documents"][0])):
                    formatted_results.append({
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i]
                    })
            
            return {
                "department": department,
                "query": query,
                "total_results": len(formatted_results),
                "results": formatted_results
            }
        else:
            # Get all documents from department
            results = collection.get(
                where={"department": department},
                limit=n_results,
                include=["documents", "metadatas"]
            )
            
            formatted_results = []
            if results and results["documents"]:
                for i in range(len(results["documents"])):
                    formatted_results.append({
                        "document": results["documents"][i],
                        "metadata": results["metadatas"][i]
                    })
            
            return {
                "department": department,
                "total_results": len(formatted_results),
                "results": formatted_results
            }
    except Exception as e:
        raise Exception(f"Failed to search by department: {str(e)}") from e


@mcp.tool()
async def get_departments() -> List[str]:
    """Get list of all unique departments in the database.
    
    Returns:
        List of department codes
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(DEFAULT_COLLECTION)
        
        # Get all metadata
        results = collection.get(include=["metadatas"])
        
        # Extract unique departments
        departments = set()
        if results and results["metadatas"]:
            for metadata in results["metadatas"]:
                dept = metadata.get("department")
                if dept:
                    departments.add(dept)
        
        return sorted(list(departments))
    except Exception as e:
        raise Exception(f"Failed to get departments: {str(e)}") from e


@mcp.tool()
async def get_programs() -> Dict:
    """Get list of all programs organized by level (UG/PG).
    
    Returns:
        Dictionary with UG and PG programs
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(DEFAULT_COLLECTION)
        
        # Get all metadata
        results = collection.get(include=["metadatas"])
        
        # Extract unique programs by level
        ug_programs = set()
        pg_programs = set()
        
        if results and results["metadatas"]:
            for metadata in results["metadatas"]:
                level = metadata.get("level")
                program = metadata.get("program_type")
                
                if level == "UG" and program:
                    ug_programs.add(program)
                elif level == "PG" and program:
                    pg_programs.add(program)
        
        return {
            "UG": sorted(list(ug_programs)),
            "PG": sorted(list(pg_programs))
        }
    except Exception as e:
        raise Exception(f"Failed to get programs: {str(e)}") from e


@mcp.tool()
async def peek_collection(
    collection_name: str = DEFAULT_COLLECTION,
    limit: int = 5
) -> Dict:
    """Peek at sample documents from the collection.
    
    Args:
        collection_name: Name of the collection
        limit: Number of documents to peek at
    
    Returns:
        Sample documents with metadata
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        results = collection.peek(limit=limit)
        
        return {
            "collection": collection_name,
            "sample_count": len(results.get("ids", [])),
            "samples": {
                "ids": results.get("ids", []),
                "documents": results.get("documents", []),
                "metadatas": results.get("metadatas", [])
            }
        }
    except Exception as e:
        raise Exception(f"Failed to peek collection: {str(e)}") from e


##### Collection Management Tools #####

@mcp.tool()
async def create_collection(
    collection_name: str,
    metadata: Dict | None = None
) -> str:
    """Create a new Chroma collection.
    
    Args:
        collection_name: Name of the collection to create
        metadata: Optional metadata dict to add to the collection
    
    Returns:
        Success message
    """
    client = get_chroma_client()
    try:
        client.create_collection(
            name=collection_name,
            metadata=metadata
        )
        return f"Successfully created collection '{collection_name}'"
    except Exception as e:
        raise Exception(f"Failed to create collection '{collection_name}': {str(e)}") from e


@mcp.tool()
async def get_or_create_collection(
    collection_name: str,
    metadata: Dict | None = None
) -> str:
    """Get an existing collection or create it if it doesn't exist.
    
    Args:
        collection_name: Name of the collection
        metadata: Optional metadata dict for the collection
    
    Returns:
        Status message
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        return f"Collection '{collection_name}' already exists with {collection.count()} documents"
    except:
        client.create_collection(
            name=collection_name,
            metadata=metadata
        )
        return f"Created new collection '{collection_name}'"


@mcp.tool()
async def delete_collection(collection_name: str) -> str:
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


@mcp.tool()
async def get_collection_count(collection_name: str = DEFAULT_COLLECTION) -> int:
    """Get the number of documents in a collection.
    
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
        raise Exception(f"Failed to get collection count: {str(e)}") from e


##### Document Operations #####

@mcp.tool()
async def add_documents(
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
                f"Use 'update_documents' to update existing documents."
            )
        
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        return f"Successfully added {len(documents)} documents to collection '{collection_name}'"
    except Exception as e:
        raise Exception(f"Failed to add documents: {str(e)}") from e


@mcp.tool()
async def get_documents(
    collection_name: str = DEFAULT_COLLECTION,
    ids: List[str] | None = None,
    where: Dict | None = None,
    limit: int | None = None,
    offset: int | None = None
) -> Dict:
    """Get documents from a Chroma collection with optional filtering.
    
    Args:
        collection_name: Name of the collection
        ids: Optional list of document IDs to retrieve
        where: Optional metadata filters
        limit: Optional maximum number of documents to return
        offset: Optional number of documents to skip
    
    Returns:
        Dictionary containing the matching documents
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        return collection.get(
            ids=ids,
            where=where,
            include=["documents", "metadatas"],
            limit=limit,
            offset=offset
        )
    except Exception as e:
        raise Exception(f"Failed to get documents: {str(e)}") from e


@mcp.tool()
async def update_documents(
    collection_name: str,
    ids: List[str],
    documents: List[str] | None = None,
    metadatas: List[Dict] | None = None
) -> str:
    """Update documents in a Chroma collection.
    
    Args:
        collection_name: Name of the collection
        ids: List of document IDs to update (required)
        documents: Optional list of new text documents
        metadatas: Optional list of new metadata dictionaries
    
    Returns:
        Confirmation message
    """
    if not ids:
        raise ValueError("The 'ids' list cannot be empty.")
    
    if documents is None and metadatas is None:
        raise ValueError("At least one of 'documents' or 'metadatas' must be provided.")
    
    if documents is not None and len(documents) != len(ids):
        raise ValueError("Length of 'documents' must match length of 'ids'.")
    if metadatas is not None and len(metadatas) != len(ids):
        raise ValueError("Length of 'metadatas' must match length of 'ids'.")
    
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        
        update_args = {"ids": ids}
        if documents is not None:
            update_args["documents"] = documents
        if metadatas is not None:
            update_args["metadatas"] = metadatas
        
        collection.update(**update_args)
        return f"Successfully updated {len(ids)} documents in collection '{collection_name}'"
    except Exception as e:
        raise Exception(f"Failed to update documents: {str(e)}") from e


@mcp.tool()
async def delete_documents(
    collection_name: str,
    ids: List[str]
) -> str:
    """Delete documents from a Chroma collection.
    
    Args:
        collection_name: Name of the collection
        ids: List of document IDs to delete
    
    Returns:
        Confirmation message
    """
    if not ids:
        raise ValueError("The 'ids' list cannot be empty.")
    
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        collection.delete(ids=ids)
        return f"Successfully deleted {len(ids)} documents from collection '{collection_name}'"
    except Exception as e:
        raise Exception(f"Failed to delete documents: {str(e)}") from e


@mcp.tool()
async def upsert_documents(
    collection_name: str,
    documents: List[str],
    ids: List[str],
    metadatas: List[Dict] | None = None
) -> str:
    """Upsert documents (add if new, update if exists).
    
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
        raise ValueError(f"Number of ids must match documents")
    
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


##### Advanced Operations #####

@mcp.tool()
async def batch_add_documents(
    collection_name: str,
    documents: List[str],
    ids: List[str],
    metadatas: List[Dict] | None = None,
    batch_size: int = 100
) -> str:
    """Add documents in batches for better performance.
    
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
        raise ValueError(f"Number of ids must match documents")
    
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
async def delete_documents_by_filter(
    collection_name: str,
    where: Dict
) -> str:
    """Delete all documents matching filters.
    
    Args:
        collection_name: Name of the collection
        where: Metadata filters
    
    Returns:
        Success message
    """
    if not where:
        raise ValueError("Filter 'where' must be provided")
    
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        collection.delete(where=where)
        return f"Successfully deleted documents from collection '{collection_name}' matching the filters"
    except Exception as e:
        raise Exception(f"Failed to delete filtered documents: {str(e)}") from e


@mcp.tool()
async def reset_collection(collection_name: str) -> str:
    """Delete all documents from a collection without deleting the collection itself.
    
    Args:
        collection_name: Name of the collection to reset
    
    Returns:
        Success message with count of deleted documents
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        
        count_before = collection.count()
        all_docs = collection.get(include=[])
        all_ids = all_docs["ids"]
        
        if all_ids:
            collection.delete(ids=all_ids)
        
        return f"Successfully reset collection '{collection_name}' - removed {count_before} documents"
    except Exception as e:
        raise Exception(f"Failed to reset collection: {str(e)}") from e


@mcp.tool()
async def count_documents_with_filter(
    collection_name: str = DEFAULT_COLLECTION,
    where: Dict | None = None
) -> int:
    """Count documents matching specific filters.
    
    Args:
        collection_name: Name of the collection
        where: Optional metadata filters
    
    Returns:
        Number of documents matching the filters
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(collection_name)
        
        results = collection.get(
            where=where,
            include=[]
        )
        
        return len(results["ids"])
    except Exception as e:
        raise Exception(f"Failed to count filtered documents: {str(e)}") from e


def main():
    """Entry point for the MCP server."""
    print("=" * 80, file=sys.stderr)
    print("🎓 KEC Syllabi MCP Server - Full Featured", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"📁 ChromaDB Path: {CHROMA_DATA_DIR}", file=sys.stderr)
    print(f"📚 Default Collection: {DEFAULT_COLLECTION}", file=sys.stderr)
    print(f"🔌 Transport: {MCP_TRANSPORT}", file=sys.stderr)
    print(f"🌐 Host: {MCP_HOST}:{MCP_PORT}", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    
    try:
        # Initialize client to verify setup
        get_chroma_client()
        print("✅ ChromaDB client initialized successfully", file=sys.stderr)
        print("\n🔧 Available Tools:", file=sys.stderr)
        print("   - Collection Management: list, create, delete, get_info", file=sys.stderr)
        print("   - Document Operations: add, get, update, delete, upsert", file=sys.stderr)
        print("   - Search & Query: query_syllabi, search_by_department", file=sys.stderr)
        print("   - Advanced: batch_add, filter operations", file=sys.stderr)
        print("   - Utilities: get_departments, get_programs, peek", file=sys.stderr)
        print("\n🚀 Starting MCP server with stdio transport...\n", file=sys.stderr)
        
        # Run the MCP server over HTTP/SSE transport
        mcp.run(transport=MCP_TRANSPORT, host=MCP_HOST, port=MCP_PORT)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}", file=sys.stderr)
        print("\nMake sure you have run the ingestion pipeline first:", file=sys.stderr)
        print("  python llamaindex_pdf_ingestion.py --source-dir \"D:\\\\2022\" --chroma-path \"./student_db_2022\"", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
