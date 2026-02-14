import os
from dotenv import load_dotenv

from llama_parse import LlamaParse
from llama_index.core import Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

import chromadb


# -----------------------
# Load environment variables
# -----------------------
load_dotenv()

LLAMA_PARSE_API_KEY = os.getenv("LLAMA_PARSE_API_KEY")

if not LLAMA_PARSE_API_KEY:
    raise ValueError("LLAMA_PARSE_API_KEY not found in .env")


# -----------------------
# Step 1: Setup LlamaParse
# -----------------------
parser = LlamaParse(
    api_key=LLAMA_PARSE_API_KEY,
    result_type="markdown",  # better for RAG
)


# -----------------------
# Step 2: Setup ChromaDB
# -----------------------
chroma_client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = chroma_client.get_or_create_collection(
    name="knowledge_base"
)

vector_store = ChromaVectorStore(
    chroma_collection=collection
)


# -----------------------
# Step 3: Setup Embedding Model
# -----------------------
embed_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

Settings.embed_model = embed_model


# -----------------------
# Step 4: Setup Ingestion Pipeline
# -----------------------
pipeline = IngestionPipeline(
    transformations=[
        SentenceSplitter(chunk_size=512, chunk_overlap=50),
        embed_model,
    ],
    vector_store=vector_store,
)


# -----------------------
# Step 5: Load All Files from Folder
# -----------------------
documents_folder = "./documents"

all_documents = []

for filename in os.listdir(documents_folder):
    file_path = os.path.join(documents_folder, filename)

    if filename.endswith(".pdf"):
        print(f"Parsing {filename} with LlamaParse...")
        docs = parser.load_data(file_path)
        all_documents.extend(docs)

    else:
        print(f"Skipping unsupported file: {filename}")


# -----------------------
# Step 6: Run Ingestion
# -----------------------
if all_documents:
    print("Running ingestion pipeline...")
    pipeline.run(documents=all_documents)
    print("✅ Ingestion complete!")
else:
    print("No documents found.")
