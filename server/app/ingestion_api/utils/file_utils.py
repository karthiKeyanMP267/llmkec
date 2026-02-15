import os
import tempfile
import uuid
from pathlib import Path
from typing import Tuple

from app.ingestion_api.utils.logger import get_logger

logger = get_logger("file_utils")


class FileManager:
    def __init__(self, uploads_dir: str):
        self.uploads_dir = Path(uploads_dir)

    def generate_doc_id(self) -> str:
        return str(uuid.uuid4())

    def validate_pdf(self, filename: str, content: bytes) -> Tuple[bool, str]:
        if not filename.lower().endswith(".pdf"):
            return False, "Only PDF files are supported"
        if len(content) == 0:
            return False, "Empty file"
        return True, ""

    async def save_upload(self, content: bytes, filename: str, doc_id: str) -> str:
        safe_name = filename.replace("/", "_").replace("\\", "_")
        suffix = Path(safe_name).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            suffix=suffix,
            prefix=f"ingestion_{doc_id}_",
        ) as temp_file:
            temp_file.write(content)
            return temp_file.name

    def delete_file(self, path: str):
        try:
            os.remove(path)
        except FileNotFoundError:
            return
