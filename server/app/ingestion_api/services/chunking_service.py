from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter


class ChunkingService:
    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.parser = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def update_params(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.parser = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def chunk_text(self, text: str):
        # Convenience for any legacy callers that pass raw text.
        return self.chunk_documents([Document(text=text)])

    def chunk_documents(self, documents):
        return self.parser.get_nodes_from_documents(documents)
