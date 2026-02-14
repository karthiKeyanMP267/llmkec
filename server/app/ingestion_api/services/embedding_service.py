from typing import Any, Dict

from sentence_transformers import SentenceTransformer

from app.ingestion_api.config import AppConfig, app_config
from app.ingestion_api.utils.logger import get_logger

logger = get_logger("embedding_service")


class EmbeddingService:
    def __init__(self, config: AppConfig):
        self.config = config
        self.model = SentenceTransformer(self.config.current_model_name)
        self.current_model_key = self.config.current_model_key

    def embed_query(self, text: str):
        return self.model.encode(text).tolist()

    def embed_documents(self, texts):
        return self.model.encode(texts).tolist()

    def switch_model(self, model_key: str) -> Dict[str, Any]:
        self.config.current_model_key = model_key
        self.model = SentenceTransformer(self.config.current_model_name)
        self.current_model_key = model_key
        info = self.config.get_model_info(model_key)
        logger.info("Switched embedding model to %s", model_key)
        return info
