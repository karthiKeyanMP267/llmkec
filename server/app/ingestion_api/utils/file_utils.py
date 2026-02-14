import os
import uuid
from pathlib import Path
from typing import Tuple

from app.ingestion_api.utils.logger import get_logger

logger = get_logger("file_utils")


class FileManager:
    def __init__(self, uploads_dir: str):
        self.uploads_dir = Path(uploads_dir)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

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
        path = self.uploads_dir / f"{doc_id}_{safe_name}"
        with open(path, "wb") as f:
            f.write(content)
        return str(path)

    def delete_file(self, path: str):
        try:
            os.remove(path)
        except FileNotFoundError:
            return
