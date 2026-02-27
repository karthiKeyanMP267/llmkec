

import logging
import os
import sys
import chromadb
from typing import List
from pathlib import Path

from dotenv import load_dotenv
from llama_index.core import Settings, SimpleDirectoryReader, Document
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.readers.file import PDFReader
from llama_index.core.storage.docstore import SimpleDocumentStore

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def fail(msg: str):
    logger.error("❌ %s", msg)
    sys.exit(1)


def ok(msg: str):
    logger.info("✅ %s", msg)


logger.info("STEP 0: Configuration")

ENV_PATH = Path(__file__).resolve().parents[1] / ".env.ingestion"
load_dotenv(ENV_PATH, override=False)


def resolve_embedding_model() -> str:
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

# ----------------------------
# 🔒 Force local-only execution
# ----------------------------
Settings.llm = None
Settings.embed_model = HuggingFaceEmbedding(
    model_name=resolve_embedding_model()
)

ok("Local embeddings + LLM disabled")


logger.info("STEP 1: Resolve paths")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data/extracted/2024")

logger.info("Data directory: %s", DATA_DIR)

if not os.path.isdir(DATA_DIR):
    fail("Data directory does not exist")

ok("Data directory exists")


logger.info("STEP 2: Discover files")

pdf_files = [
    f for f in os.listdir(DATA_DIR)
    if f.lower().endswith(".pdf")
]

logger.info("PDF files found: %s", pdf_files)

if not pdf_files:
    fail("No PDF files found in data directory")

ok("Found %d PDF file(s)" % len(pdf_files))


logger.info("STEP 3: Load documents via PDFReader")

documents: List[Document] = SimpleDirectoryReader(
    input_dir=DATA_DIR,
    recursive=True,
    file_extractor={".pdf": PDFReader()}
).load_data()

logger.info("Documents loaded: %d", len(documents))

if not documents:
    fail("PDFReader failed to load documents")

# Optional: inspect first document
sample = documents[0].text[:300]
logger.info("Sample document text (first 300 chars):\n%s", sample)

ok("Documents successfully parsed")


logger.info("STEP 4: Initialize Chroma vector store")

CHROMA_PATH = os.path.join(PROJECT_ROOT, "student_db_2024")
COLLECTION_NAME = "rag_demo"

client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection(COLLECTION_NAME)

logger.info("Chroma collection name: %s", collection.name)

ok("Chroma collection ready")


logger.info("STEP 5: Build ingestion pipeline")

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


logger.info("STEP 6: Run ingestion")

nodes =pipeline.run(documents=documents)


ok("Pipeline execution completed")

logger.info("Nodes created: %d", len(nodes))

vector_store = ChromaVectorStore(chroma_collection=collection)
vector_store.add(nodes)
logger.info("STEP 7: Verify vector count")

count = collection.count()
logger.info("Vector count: %d", count)

if count == 0:
    fail("No vectors stored — ingestion failed")

ok("Vectors successfully stored in Chroma")

logger.info("INGESTION PIPELINE VERIFIED END-TO-END")
