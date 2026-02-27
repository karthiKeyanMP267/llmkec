import os
from pathlib import Path

from dotenv import load_dotenv
from llama_parse import LlamaParse

from app.ingestion_api.utils.logger import get_logger

logger = get_logger(__name__)


# Ensure we load the env file even when uvicorn is started from repo root
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_PATH)


def extract_with_llamaparse(file_path: str):
    api_key = os.getenv("LLAMA_PARSE_API_KEY")
    if not api_key:
        logger.error("LLAMA_PARSE_API_KEY is not set")
        return []

    parser = LlamaParse(api_key=api_key, result_type="markdown")
    documents = parser.load_data(file_path)
    return documents
