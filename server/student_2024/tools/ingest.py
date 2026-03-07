

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

# Multiple data directories to ingest
DATA_DIRS = [
    os.path.join(PROJECT_ROOT, "data/extracted/2024"),  # R2024 regulations
    os.path.join(PROJECT_ROOT, "data/ocr"),              # R2024 department syllabi
    os.path.join(PROJECT_ROOT, "data/text"),             # R2022 syllabi
]

for data_dir in DATA_DIRS:
    logger.info("Data directory: %s", data_dir)
    if not os.path.isdir(data_dir):
        logger.warning("Directory does not exist: %s", data_dir)
    else:
        ok(f"Directory exists: {data_dir}")


logger.info("STEP 2: Discover files")

pdf_files = []
for data_dir in DATA_DIRS:
    if os.path.isdir(data_dir):
        dir_pdfs = [f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]
        pdf_files.extend(dir_pdfs)
        logger.info("PDF files in %s: %s", os.path.basename(data_dir), dir_pdfs)

logger.info("Total PDF files found: %d", len(pdf_files))

if not pdf_files:
    fail("No PDF files found in any data directory")

ok("Found %d PDF file(s)" % len(pdf_files))


logger.info("STEP 3: Initialize Chroma vector store")

CHROMA_PATH = os.path.join(PROJECT_ROOT, "student_db_2024")
COLLECTION_NAME = "student_2024_collection"

client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_or_create_collection(COLLECTION_NAME)

logger.info("Chroma collection name: %s", collection.name)

ok("Chroma collection ready")


logger.info("STEP 4: Build ingestion pipeline")

docstore = SimpleDocumentStore()

def create_pipeline():
    return IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=700, chunk_overlap=300),
            Settings.embed_model, 
        ],
        vector_store=ChromaVectorStore(chroma_collection=collection),
        docstore=docstore
    )

ok("IngestionPipeline created")


logger.info("STEP 5: Process each directory")

BATCH_SIZE = 50  # Process 50 documents at a time
total_nodes = 0
total_docs = 0

for dir_idx, data_dir in enumerate(DATA_DIRS):
    if not os.path.isdir(data_dir):
        continue
    
    dir_name = os.path.basename(data_dir)
    logger.info("=" * 50)
    logger.info("Processing directory %d/%d: %s", dir_idx + 1, len(DATA_DIRS), dir_name)
    
    # Load documents from this directory
    try:
        dir_docs = SimpleDirectoryReader(
            input_dir=data_dir,
            recursive=True,
            file_extractor={".pdf": PDFReader()}
        ).load_data()
        logger.info("Loaded %d documents from %s", len(dir_docs), dir_name)
    except Exception as e:
        logger.error("Failed to load documents from %s: %s", dir_name, str(e))
        continue
    
    total_docs += len(dir_docs)
    
    # Process in batches
    for i in range(0, len(dir_docs), BATCH_SIZE):
        batch = dir_docs[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(dir_docs) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info("[%s] Batch %d/%d (%d docs)...", dir_name, batch_num, total_batches, len(batch))
        
        try:
            pipeline = create_pipeline()
            nodes = pipeline.run(documents=batch)
            total_nodes += len(nodes)
            logger.info("[%s] Batch %d complete: %d nodes", dir_name, batch_num, len(nodes))
        except Exception as e:
            logger.error("[%s] Batch %d failed: %s", dir_name, batch_num, str(e))
            continue
    
    ok(f"Directory {dir_name} complete")

ok("All directories processed")

logger.info("Total documents processed: %d", total_docs)
logger.info("Total nodes created: %d", total_nodes)

logger.info("STEP 6: Verify vector count")

count = collection.count()
logger.info("Vector count: %d", count)

if count == 0:
    fail("No vectors stored — ingestion failed")

ok("Vectors successfully stored in Chroma")

logger.info("INGESTION PIPELINE VERIFIED END-TO-END")
