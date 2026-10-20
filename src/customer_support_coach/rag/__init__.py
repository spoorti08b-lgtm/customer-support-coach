"""RAG module: PDF ingestion, chunking, embeddings, ChromaDB, top-k retrieval.

Public API::

    from customer_support_coach.rag import RagPipeline, RagConfig
"""

from .chunker import TextChunker
from .config import RagConfig
from .document_loader import PdfDocumentLoader, clean_text, make_doc_id
from .embeddings import EmbeddingProvider, OnnxMiniLMEmbedder, create_embedder
from .models import (
    Chunk,
    DocumentLoadError,
    DocumentNotFoundError,
    EmbeddingError,
    EmbeddingModelMismatchError,
    EmptyDocumentError,
    InvalidInputError,
    InvalidQueryError,
    LoadedDocument,
    NoExtractableTextError,
    PageText,
    RagError,
    UnreadableDocumentError,
    VectorStoreError,
)
from .pipeline import IngestionReport, IngestionResult, RagPipeline
from .retriever import RetrievalResult, Retriever
from .vector_store import ChromaVectorStore

__all__ = [
    "RagPipeline", "RagConfig", "IngestionReport", "IngestionResult",
    "RetrievalResult", "Retriever", "ChromaVectorStore", "TextChunker",
    "PdfDocumentLoader", "clean_text", "make_doc_id", "EmbeddingProvider",
    "OnnxMiniLMEmbedder", "create_embedder", "Chunk", "LoadedDocument", "PageText",
    "RagError", "InvalidInputError", "InvalidQueryError", "DocumentLoadError",
    "DocumentNotFoundError", "UnreadableDocumentError", "EmptyDocumentError",
    "NoExtractableTextError", "EmbeddingError", "VectorStoreError",
    "EmbeddingModelMismatchError",
]
