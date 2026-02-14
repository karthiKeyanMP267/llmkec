"""
LlamaIndex PDF Ingestion Pipeline for KEC Syllabi & Regulations
Recursively processes all PDFs from D:\2022\ and stores in ChromaDB

Features:
- Recursive PDF discovery with metadata extraction
- Path-based categorization (UG/PG, BE/BTECH/MBA/etc, Curricula/Regulations)
- Automatic chunking and embedding with LlamaIndex
- ChromaDB storage with rich metadata
- Progress tracking and error handling
- Compatible with existing MCP server

Usage:
    python llamaindex_pdf_ingestion.py --source-dir "D:\\2022" --chroma-path "./student_db_2022"
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import argparse
from datetime import datetime
import json

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    Settings,
    Document
)
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb
from tqdm import tqdm


class KEC_PDF_Ingestion_Pipeline:
    """
    Complete pipeline for ingesting KEC syllabi and regulations into ChromaDB
    using LlamaIndex for processing and indexing
    """
    
    def __init__(
        self,
        source_dir: str,
        chroma_path: str = "./student_db_2022",
        collection_name: str = "kec_syllabi_regulations_r2022",
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ):
        """
        Initialize the ingestion pipeline
        
        Args:
            source_dir: Root directory containing PDFs (e.g., "D:\\2022")
            chroma_path: Path for ChromaDB storage
            collection_name: Name for the ChromaDB collection
            embedding_model: HuggingFace model for embeddings (local, no API cost)
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self.source_dir = Path(source_dir)
        self.chroma_path = chroma_path
        self.collection_name = collection_name
        
        print("=" * 80)
        print("🎓 KEC PDF Ingestion Pipeline - LlamaIndex + ChromaDB")
        print("=" * 80)
        
        # Validate source directory
        if not self.source_dir.exists():
            raise ValueError(f"Source directory not found: {source_dir}")
        
        print(f"\n📂 Source Directory: {self.source_dir}")
        print(f"💾 ChromaDB Path: {chroma_path}")
        print(f"📊 Collection Name: {collection_name}")
        
        # Configure LlamaIndex Settings
        print(f"\n⚙️  Loading embedding model: {embedding_model}")
        Settings.embed_model = HuggingFaceEmbedding(model_name=embedding_model)
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap
        
        print(f"   - Chunk size: {chunk_size}")
        print(f"   - Chunk overlap: {chunk_overlap}")
        
        # Initialize ChromaDB
        print(f"\n🗄️  Initializing ChromaDB...")
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        
        # Delete existing collection if it exists (for fresh ingestion)
        try:
            self.chroma_client.delete_collection(name=collection_name)
            print(f"   ⚠️  Deleted existing collection: {collection_name}")
        except:
            pass
        
        # Create new collection
        self.collection = self.chroma_client.create_collection(
            name=collection_name,
            metadata={"description": "KEC Syllabi and Regulations R2022"}
        )
        print(f"   ✓ Created collection: {collection_name}")
        
        # Statistics
        self.stats = {
            "total_pdfs": 0,
            "successful": 0,
            "failed": 0,
            "total_chunks": 0,
            "failed_files": []
        }
    
    def discover_pdfs(self) -> List[Path]:
        """
        Recursively discover all PDF files in the source directory
        
        Returns:
            List of Path objects for PDF files
        """
        print(f"\n🔍 Discovering PDF files...")
        pdf_files = list(self.source_dir.rglob("*.pdf"))
        
        # Filter out temporary files
        pdf_files = [f for f in pdf_files if not f.name.startswith("~$")]
        
        print(f"   ✓ Found {len(pdf_files)} PDF files")
        self.stats["total_pdfs"] = len(pdf_files)
        
        return pdf_files
    
    def extract_metadata_from_path(self, pdf_path: Path) -> Dict[str, str]:
        """
        Extract structured metadata from file path
        
        Example path: D:/2022/Curricula and Syllabi/UG/BE/KEC-R2022-CSE.pdf
        Extracts:
            - category: "Curricula and Syllabi" or "Regulations"
            - level: "UG" or "PG"
            - program_type: "BE", "BTECH", "MBA", etc.
            - department: "CSE", "ECE", etc.
            - filename: Original filename
        """
        parts = pdf_path.parts
        relative_parts = parts[parts.index(self.source_dir.name) + 1:]
        
        metadata = {
            "source_file": pdf_path.name,
            "full_path": str(pdf_path),
            "regulation": "R2022"
        }
        
        # Extract category (Curricula/Regulations)
        if len(relative_parts) > 0:
            metadata["category"] = relative_parts[0]  # "Curricula and Syllabi" or "Regulations"
        
        # Extract level (UG/PG)
        if len(relative_parts) > 1:
            metadata["level"] = relative_parts[1]  # "UG" or "PG"
        
        # Extract program type (BE/BTECH/MBA/etc)
        if len(relative_parts) > 2:
            metadata["program_type"] = relative_parts[2]  # "BE", "BTECH", "MBA", etc.
        
        # Extract department from filename
        filename = pdf_path.stem  # Without extension
        
        # Parse department from patterns like "KEC-R2022-CSE" or "R2022-MBA"
        if "-" in filename:
            parts = filename.split("-")
            if len(parts) >= 2:
                metadata["department"] = parts[-1]  # Last part is usually department
        
        return metadata
    
    def process_pdf_with_metadata(self, pdf_path: Path) -> List[Document]:
        """
        Process a single PDF and return LlamaIndex Documents with metadata
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of Document objects with extracted text and metadata
        """
        try:
            # Extract metadata from path
            metadata = self.extract_metadata_from_path(pdf_path)
            
            # Load PDF using LlamaIndex SimpleDirectoryReader
            reader = SimpleDirectoryReader(
                input_files=[str(pdf_path)],
                file_metadata=lambda _: metadata  # Attach metadata to all chunks
            )
            documents = reader.load_data()
            
            return documents
        
        except Exception as e:
            print(f"      ❌ Error: {str(e)}")
            self.stats["failed"] += 1
            self.stats["failed_files"].append({
                "file": pdf_path.name,
                "error": str(e)
            })
            return []
    
    def ingest_all_pdfs(self):
        """
        Main ingestion pipeline - process all PDFs and store in ChromaDB
        """
        # Discover PDFs
        pdf_files = self.discover_pdfs()
        
        if len(pdf_files) == 0:
            print("⚠️  No PDF files found!")
            return
        
        print(f"\n📚 Processing {len(pdf_files)} PDF files...")
        print("=" * 80)
        
        all_documents = []
        
        # Process each PDF with progress bar
        for pdf_path in tqdm(pdf_files, desc="Processing PDFs", unit="file"):
            tqdm.write(f"\n📄 Processing: {pdf_path.name}")
            tqdm.write(f"   Path: {pdf_path.relative_to(self.source_dir)}")
            
            documents = self.process_pdf_with_metadata(pdf_path)
            
            if documents:
                all_documents.extend(documents)
                self.stats["successful"] += 1
                tqdm.write(f"   ✓ Extracted {len(documents)} pages/chunks")
            else:
                tqdm.write(f"   ⚠️  Failed to process")
        
        print("\n" + "=" * 80)
        print(f"📊 Extraction Complete:")
        print(f"   - Total PDFs: {self.stats['total_pdfs']}")
        print(f"   - Successful: {self.stats['successful']}")
        print(f"   - Failed: {self.stats['failed']}")
        print(f"   - Total document chunks: {len(all_documents)}")
        
        if self.stats["failed"] > 0:
            print(f"\n⚠️  Failed files:")
            for item in self.stats["failed_files"]:
                print(f"   - {item['file']}: {item['error']}")
        
        # Create vector index and store in ChromaDB
        if len(all_documents) > 0:
            print("\n" + "=" * 80)
            print("🔄 Creating vector index and storing in ChromaDB...")
            print("   (This may take a few minutes depending on document count)")
            
            vector_store = ChromaVectorStore(chroma_collection=self.collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            
            # Create index (automatically chunks, embeds, and stores)
            index = VectorStoreIndex.from_documents(
                all_documents,
                storage_context=storage_context,
                show_progress=True
            )
            
            # Get final chunk count from ChromaDB
            collection_count = self.collection.count()
            self.stats["total_chunks"] = collection_count
            
            print(f"\n✅ Ingestion Complete!")
            print(f"   - Total chunks stored: {collection_count}")
            print(f"   - ChromaDB collection: {self.collection_name}")
            print(f"   - Storage path: {self.chroma_path}")
            
            # Save statistics
            self._save_stats()
        else:
            print("\n⚠️  No documents to ingest!")
    
    def _save_stats(self):
        """Save ingestion statistics to JSON file"""
        stats_file = Path(self.chroma_path) / f"{self.collection_name}_stats.json"
        
        self.stats["timestamp"] = datetime.now().isoformat()
        self.stats["source_directory"] = str(self.source_dir)
        self.stats["collection_name"] = self.collection_name
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)
        
        print(f"\n📊 Statistics saved to: {stats_file}")
    
    def test_query(self, query: str = "What are the course prerequisites?"):
        """
        Test the ingested data with a sample query
        
        Args:
            query: Test query string
        """
        print("\n" + "=" * 80)
        print("🔍 Testing Query Engine...")
        print("=" * 80)
        
        vector_store = ChromaVectorStore(chroma_collection=self.collection)
        index = VectorStoreIndex.from_vector_store(vector_store)
        
        query_engine = index.as_query_engine(similarity_top_k=3)
        
        print(f"\n❓ Query: {query}")
        print("\n🤖 Response:")
        print("-" * 80)
        
        response = query_engine.query(query)
        print(response)
        
        print("\n📚 Source Documents:")
        print("-" * 80)
        for i, node in enumerate(response.source_nodes, 1):
            print(f"\n{i}. Source: {node.metadata.get('source_file', 'Unknown')}")
            print(f"   Department: {node.metadata.get('department', 'N/A')}")
            print(f"   Level: {node.metadata.get('level', 'N/A')}")
            print(f"   Snippet: {node.text[:200]}...")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="LlamaIndex PDF Ingestion Pipeline for KEC Syllabi"
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        help="Source directory containing PDFs (e.g., D:\\\\2022)"
    )
    parser.add_argument(
        "--chroma-path",
        default="./student_db_2022",
        help="Path for ChromaDB storage (default: ./student_db_2022)"
    )
    parser.add_argument(
        "--collection",
        default="kec_syllabi_regulations_r2022",
        help="ChromaDB collection name"
    )
    parser.add_argument(
        "--embedding-model",
        default="BAAI/bge-small-en-v1.5",
        help="HuggingFace embedding model (default: BAAI/bge-small-en-v1.5)"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Chunk size for text splitting (default: 512)"
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Overlap between chunks (default: 50)"
    )
    parser.add_argument(
        "--test-query",
        action="store_true",
        help="Run a test query after ingestion"
    )
    parser.add_argument(
        "--query",
        default="What are the course prerequisites?",
        help="Test query string (only used with --test-query)"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize pipeline
        pipeline = KEC_PDF_Ingestion_Pipeline(
            source_dir=args.source_dir,
            chroma_path=args.chroma_path,
            collection_name=args.collection,
            embedding_model=args.embedding_model,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap
        )
        
        # Run ingestion
        pipeline.ingest_all_pdfs()
        
        # Test query if requested
        if args.test_query:
            pipeline.test_query(query=args.query)
        
        print("\n" + "=" * 80)
        print("✅ Pipeline Complete!")
        print("=" * 80)
        print("\n🚀 Next Steps:")
        print("   1. Use your existing MCP server to query the collection")
        print("   2. Collection name: " + args.collection)
        print("   3. ChromaDB path: " + args.chroma_path)
        print("\n💡 MCP Server Usage:")
        print("   Run: python chromaDB_MCP/mcp_chroma_server.py \\")
        print("        --client-type persistent \\")
        print(f"        --data-dir {args.chroma_path}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
