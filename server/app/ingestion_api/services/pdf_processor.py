import os
from pathlib import Path

from dotenv import load_dotenv
from llama_parse import LlamaParse

from app.ingestion_api.utils.logger import get_logger

logger = get_logger(__name__)


# Ensure the LLAMA_PARSE_API_KEY from the repo-level .env is available when uvicorn starts from different cwd.
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_ENV_PATH)


class PDFProcessorService:
    def __init__(self):
        api_key = os.getenv("LLAMA_PARSE_API_KEY")
        if not api_key:
            logger.error("LLAMA_PARSE_API_KEY is not set")
        self.api_key = api_key

    def extract(self, file_path: str):
        """Parse PDF with LlamaParse and return llama-index Documents plus page count."""
        if not self.api_key:
            logger.error("Cannot extract PDF — LLAMA_PARSE_API_KEY is not set")
            return [], 0
        # Create parser per call to avoid stale event loop issues between background tasks.
        parser = LlamaParse(api_key=self.api_key, result_type="markdown")
        documents = parser.load_data(file_path)
        pages = len(documents)
        return documents, pages
