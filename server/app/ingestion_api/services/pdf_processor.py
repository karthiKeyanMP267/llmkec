import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from llama_parse import LlamaParse

from app.ingestion_api.utils.logger import get_logger

logger = get_logger(__name__)


# Ensure the LLAMA_PARSE_API_KEY from the repo-level .env is available when uvicorn starts from different cwd.
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_ENV_PATH)


class PDFProcessorService:
    def __init__(self, api_key: Optional[str] = None):
        resolved_key = api_key or os.getenv("LLAMA_PARSE_API_KEY") or ""
        self.api_key = resolved_key.strip()
        if self.api_key:
            os.environ["LLAMA_PARSE_API_KEY"] = self.api_key
        else:
            logger.error("LLAMA_PARSE_API_KEY is not set")

    def _persist_to_env(self, api_key: str):
        try:
            existing = []
            if _ENV_PATH.exists():
                existing = _ENV_PATH.read_text().splitlines()
            updated = False
            for idx, line in enumerate(existing):
                if line.startswith("LLAMA_PARSE_API_KEY="):
                    existing[idx] = f"LLAMA_PARSE_API_KEY={api_key}"
                    updated = True
            if not updated:
                existing.append(f"LLAMA_PARSE_API_KEY={api_key}")
            _ENV_PATH.write_text("\n".join(existing) + ("\n" if existing else ""))
        except Exception as exc:  # best-effort persist
            logger.error("Failed to persist LlamaParse API key to .env: %s", exc)

    def set_api_key(self, api_key: str, persist: bool = True):
        clean_key = (api_key or "").strip()
        if not clean_key:
            raise ValueError("LlamaParse API key cannot be empty")
        self.api_key = clean_key
        os.environ["LLAMA_PARSE_API_KEY"] = clean_key
        if persist:
            self._persist_to_env(clean_key)
        logger.info("Updated LlamaParse API key%s", " and persisted to .env" if persist else "")

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
