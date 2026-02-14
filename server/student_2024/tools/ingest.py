

import os
import sys
import chromadb
from typing import List

from llama_index.core import Settings, SimpleDirectoryReader, Document
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.readers.file import PDFReader
from llama_index.core.storage.docstore import SimpleDocumentStore



def fail(msg: str):
    print(f"❌ {msg}")
    sys.exit(1)


def ok(msg: str):
    print(f"✅ {msg}")


print("\n🔍 STEP 0: Configuration")

# ----------------------------
# 🔒 Force local-only execution
# ----------------------------
Settings.llm = None
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-base-en-v1.5"
)

ok("Local embeddings + LLM disabled")


print("\n📁 STEP 1: Resolve paths")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data/extracted/2024")

print("📂 Data directory:", DATA_DIR)

if not os.path.isdir(DATA_DIR):
    fail("Data directory does not exist")

ok("Data directory exists")


print("\n📄 STEP 2: Discover files")

pdf_files = [
    f for f in os.listdir(DATA_DIR)
    if f.lower().endswith(".pdf")
]

print("📄 PDF files found:", pdf_files)

if not pdf_files:
    fail("No PDF files found in data directory")

ok(f"Found {len(pdf_files)} PDF file(s)")


print("\n📄 STEP 3: Load documents via PDFReader")

documents: List[Document] = SimpleDirectoryReader(
    input_dir=DATA_DIR,
    recursive=True,
    file_extractor={".pdf": PDFReader()}
).load_data()

print("📄 Documents loaded:", len(documents))

if not documents:
    fail("PDFReader failed to load documents")

# Optional: inspect first document
sample = documents[0].text[:300]
print("\n📄 Sample document text (first 300 chars):")
print(sample)

ok("Documents successfully parsed")


print("\n🧱 STEP 4: Initialize Chroma vector store")

CHROMA_PATH = os.path.join(PROJECT_ROOT, "student_db_2024")
COLLECTION_NAME = "rag_demo"

client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection(COLLECTION_NAME)

print("📦 Chroma collection name:", collection.name)

ok("Chroma collection ready")


print("\n🔗 STEP 5: Build ingestion pipeline")

docstore = SimpleDocumentStore()
pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=700, chunk_overlap=300),
        Settings.embed_model, 
    ],
    vector_store=ChromaVectorStore(chroma_collection=collection),
    docstore=docstore
)
ok("IngestionPipeline created")


print("\n🚀 STEP 6: Run ingestion")

nodes =pipeline.run(documents=documents)


ok("Pipeline execution completed")

print("🧩 Nodes created:", len(nodes))

vector_store = ChromaVectorStore(chroma_collection=collection)
vector_store.add(nodes)
print("\n📊 STEP 7: Verify vector count")

count = collection.count()
print("📊 Vector count:", count)

if count == 0:
    fail("No vectors stored — ingestion failed")

ok("Vectors successfully stored in Chroma")

print("\n🎉 INGESTION PIPELINE VERIFIED END-TO-END\n")
