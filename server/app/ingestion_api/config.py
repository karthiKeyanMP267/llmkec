"""
Application configuration for the embedded auto-ingestion pipeline.
"""

import os
from pathlib import Path
from typing import Optional


class AppConfig:
    AVAILABLE_MODELS = {
        "bge-large-en-v1.5": {
            "model_name": "BAAI/bge-large-en-v1.5",
            "dimensions": 1024,
            "description": "Best quality, slower. Recommended for production.",
        },
        "e5-large-v2": {
            "model_name": "intfloat/e5-large-v2",
            "dimensions": 1024,
            "description": "High quality, good for general text.",
        },
        "gte-large": {
            "model_name": "thenlper/gte-large",
            "dimensions": 1024,
            "description": "Strong general-purpose embeddings.",
        },
        "bge-base-en-v1.5": {
            "model_name": "BAAI/bge-base-en-v1.5",
            "dimensions": 768,
            "description": "Good balance of quality and speed.",
        },
        "e5-base-v2": {
            "model_name": "intfloat/e5-base-v2",
            "dimensions": 768,
            "description": "Balanced quality and performance.",
        },
        "all-MiniLM-L6-v2": {
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "dimensions": 384,
            "description": "Fastest, lightest. Good for prototyping.",
        },
    }

    def __init__(self):
        base_dir = Path(__file__).parent.parent.parent.resolve()
        self._base_dir = base_dir

        env_chroma = os.getenv("CHROMA_DATA_DIR")
        env_uploads = os.getenv("UPLOADS_DIR")
        env_metadata = os.getenv("METADATA_DB_PATH")

        self._chroma_data_dir = self._resolve_path(env_chroma, base_dir / "storage" / "chroma")
        self._uploads_dir = self._resolve_path(env_uploads, base_dir / "storage" / "uploads")
        self._metadata_db_path = self._resolve_path(env_metadata, base_dir / "storage" / "ingestion_metadata.db")

        self._chroma_data_dir.mkdir(parents=True, exist_ok=True)
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        self._metadata_db_path.parent.mkdir(parents=True, exist_ok=True)

        self._current_model_key = os.getenv("EMBEDDING_MODEL", "bge-base-en-v1.5")
        self._chunk_size = int(os.getenv("CHUNK_SIZE", "700"))
        self._chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "300"))
        self._default_collection = os.getenv("DEFAULT_COLLECTION", "auto_ingestion_docs")

        self._host = os.getenv("API_HOST", "0.0.0.0")
        self._port = int(os.getenv("API_PORT", "8000"))

    def _resolve_path(self, raw: Optional[str], default: Path) -> Path:
        if not raw:
            return default
        candidate = Path(raw).expanduser()
        return candidate if candidate.is_absolute() else (self._base_dir / candidate)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    @property
    def chroma_data_dir(self) -> str:
        return str(self._chroma_data_dir)

    @property
    def uploads_dir(self) -> str:
        return str(self._uploads_dir)

    @property
    def metadata_db_path(self) -> str:
        return str(self._metadata_db_path)

    @property
    def current_model_key(self) -> str:
        return self._current_model_key

    @current_model_key.setter
    def current_model_key(self, value: str):
        if value not in self.AVAILABLE_MODELS:
            raise ValueError(f"Unknown model: {value}")
        self._current_model_key = value

    @property
    def current_model_name(self) -> str:
        return self.AVAILABLE_MODELS[self._current_model_key]["model_name"]

    @property
    def current_model_dimensions(self) -> int:
        return self.AVAILABLE_MODELS[self._current_model_key]["dimensions"]

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @chunk_size.setter
    def chunk_size(self, value: int):
        if value < 64 or value > 4096:
            raise ValueError("Chunk size must be between 64 and 4096")
        self._chunk_size = value

    @property
    def chunk_overlap(self) -> int:
        return self._chunk_overlap

    @chunk_overlap.setter
    def chunk_overlap(self, value: int):
        if value < 0 or value >= self._chunk_size:
            raise ValueError("Chunk overlap must be between 0 and chunk_size-1")
        self._chunk_overlap = value

    @property
    def default_collection(self) -> str:
        return self._default_collection

    @default_collection.setter
    def default_collection(self, value: str):
        self._default_collection = value

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def get_model_info(self, model_key: Optional[str] = None) -> dict:
        key = model_key or self._current_model_key
        if key not in self.AVAILABLE_MODELS:
            raise ValueError(f"Unknown model: {key}")
        info = self.AVAILABLE_MODELS[key].copy()
        info["key"] = key
        info["is_current"] = key == self._current_model_key
        return info

    def list_available_models(self) -> list:
        models = []
        for key, info in self.AVAILABLE_MODELS.items():
            entry = info.copy()
            entry["key"] = key
            entry["is_current"] = key == self._current_model_key
            models.append(entry)
        return models

    def to_dict(self) -> dict:
        return {
            "embedding_model": {
                "key": self._current_model_key,
                "model_name": self.current_model_name,
                "dimensions": self.current_model_dimensions,
            },
            "chunking": {
                "chunk_size": self._chunk_size,
                "chunk_overlap": self._chunk_overlap,
            },
            "paths": {
                "chroma_data_dir": self.chroma_data_dir,
                "uploads_dir": self.uploads_dir,
                "metadata_db": self.metadata_db_path,
            },
            "default_collection": self._default_collection,
            "server": {"host": self._host, "port": self._port},
        }


app_config = AppConfig()
