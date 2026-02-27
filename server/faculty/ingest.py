"""
Script to ingest JSON documents into ChromaDB with sentence transformer embeddings.

This script:
1. Loads all JSON files from the json_data folder
2. Extracts document chunks and their metadata
3. Generates embeddings using sentence transformers
4. Stores everything in ChromaDB
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class JSONToChromaIngester:
    """Ingests JSON documents into ChromaDB with embeddings."""
    
    def __init__(
        self, 
        json_data_dir: str,
        model_name: str = "all-MiniLM-L6-v2",
        collection_name: str = "policy_documents",
        chroma_db_path: str = "./chroma_data"
    ):
        """
        Initialize the ingester.
        
        Args:
            json_data_dir: Path to folder containing JSON files
            model_name: Sentence transformer model to use
            collection_name: Name of ChromaDB collection
            chroma_db_path: Path where ChromaDB will store data
        """
        self.json_data_dir = json_data_dir
        self.model_name = model_name
        self.collection_name = collection_name
        self.chroma_db_path = chroma_db_path
        
        # Initialize sentence transformer
        logger.info("Loading sentence transformer model: %s", model_name)
        self.model = SentenceTransformer(model_name)
        
        # Initialize ChromaDB with modern API
        logger.info("Initializing ChromaDB at: %s", chroma_db_path)
        self.client = chromadb.PersistentClient(path=chroma_db_path)
        
        # Create or get collection
        try:
            self.client.delete_collection(name=collection_name)
            logger.info("Deleted existing collection: %s", collection_name)
        except Exception:
            logger.debug("Collection '%s' not found, skipping delete", collection_name)
        
        self.collection = self.client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("Created collection: %s", collection_name)
    
    def load_json_files(self) -> List[Dict[str, Any]]:
        """
        Load all JSON files from the json_data directory.
        
        Returns:
            List of all documents from all JSON files with source file info
        """
        all_documents = []
        json_files = list(Path(self.json_data_dir).glob("*.json"))
        
        logger.info("Found %d JSON files", len(json_files))
        
        for json_file in json_files:
            logger.info("  - Loading: %s", json_file.name)
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Get filename without extension for prefixing IDs
                    file_prefix = json_file.stem.replace(" ", "_").replace("-", "_")
                    
                    if isinstance(data, list):
                        # Add source file info to each document
                        for doc in data:
                            doc['_source_file'] = json_file.name
                            doc['_file_prefix'] = file_prefix
                            all_documents.append(doc)
                    else:
                        data['_source_file'] = json_file.name
                        data['_file_prefix'] = file_prefix
                        all_documents.append(data)
            except Exception as e:
                logger.error("    Failed to load %s: %s", json_file.name, e)
        
        logger.info("Total documents loaded: %d", len(all_documents))
        return all_documents
    
    def ingest_to_chroma(self) -> None:
        """Load JSON files and ingest them into ChromaDB with embeddings."""
        
        # Load all JSON documents
        documents = self.load_json_files()
        
        if not documents:
            logger.warning("No documents found to ingest!")
            return
        
        # Prepare data for ChromaDB
        ids = []
        texts = []
        metadatas = []
        
        logger.info("Preparing %d documents for ingestion...", len(documents))
        
        for doc in documents:
            # Extract ID and make it unique by prefixing with source file
            doc_id = doc.get("id", "")
            if not doc_id:
                continue
            
            # Create unique ID by combining file prefix with original ID
            file_prefix = doc.get("_file_prefix", "unknown")
            unique_id = f"{file_prefix}_{doc_id}"
            
            # Extract document text
            doc_text = doc.get("document", "")
            if not doc_text:
                continue
            
            # Extract metadata and add source file info
            metadata = doc.get("metadata", {})
            metadata["source_file"] = doc.get("_source_file", "unknown")
            
            ids.append(unique_id)
            texts.append(doc_text)
            metadatas.append(metadata)
        
        if not ids:
            logger.warning("No valid documents found!")
            return
        
        logger.info("Generating embeddings for %d documents...", len(texts))
        # Generate embeddings
        embeddings = self.model.encode(texts, show_progress_bar=True)
        
        # Add to ChromaDB
        logger.info("Adding documents to ChromaDB collection...")
        self.collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas
        )
        
        logger.info("Successfully ingested %d documents into ChromaDB!", len(ids))
        logger.info("  Collection name: %s", self.collection_name)
        logger.info("  ChromaDB path: %s", self.chroma_db_path)
    
    def query(self, query_text: str, n_results: int = 5) -> Dict[str, Any]:
        """
        Query the ChromaDB collection.
        
        Args:
            query_text: Text to query
            n_results: Number of results to return
            
        Returns:
            Query results
        """
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return results
    
    def print_stats(self) -> None:
        """Print collection statistics."""
        count = self.collection.count()
        logger.info("Collection Statistics:")
        logger.info("  Total documents: %d", count)


def main():
    """Main function to run the ingester."""
    
    # Paths
    script_dir = Path(__file__).parent
    json_data_dir = script_dir / "json_data"
    chroma_db_path = script_dir / "chroma_data"
    
    # Verify json_data directory exists
    if not json_data_dir.exists():
        logger.error("json_data directory not found at %s", json_data_dir)
        sys.exit(1)
    
    # Create ingester
    ingester = JSONToChromaIngester(
        json_data_dir=str(json_data_dir),
        model_name="all-MiniLM-L6-v2",  # Fast and effective model
        collection_name="policy_documents",
        chroma_db_path=str(chroma_db_path)
    )
    
    # Ingest documents
    ingester.ingest_to_chroma()
    
    # Print statistics
    ingester.print_stats()
    
    # Example query
    logger.info("=" * 60)
    logger.info("Example Query")
    logger.info("=" * 60)
    query_text = "Leave policy for faculty"
    logger.info("Query: %s", query_text)
    
    results = ingester.query(query_text, n_results=3)
    
    for i, (doc_id, text, metadata, distance) in enumerate(
        zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ),
        1
    ):
        logger.info("Result %d:", i)
        logger.info("  ID: %s", doc_id)
        logger.info("  Distance: %.4f", distance)
        logger.info("  Metadata: %s", metadata)
        logger.info("  Text preview: %s...", text[:200])


if __name__ == "__main__":
    main()
