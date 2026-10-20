"""Shared exceptions and plain data containers for the RAG module.

Nothing in here depends on ChromaDB, pypdf, or any other
``customer_support_coach`` module, so it is safe to import anywhere.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------- errors
class RagError(Exception):
    """Base class for every error raised on purpose by the RAG module."""


class InvalidInputError(RagError, ValueError):
    """A caller passed an argument that can never be valid."""


class InvalidQueryError(RagError, ValueError):
    """The search query is empty or not a string."""


class DocumentLoadError(RagError):
    """A PDF could not be turned into usable text."""

    def __init__(self, path: Path | str, message: str):
        self.path = str(path)
        self.reason = message
        super().__init__(f"{message} [{self.path}]")


class DocumentNotFoundError(DocumentLoadError):
    """The file or directory does not exist."""


class UnreadableDocumentError(DocumentLoadError):
    """The file is corrupted, encrypted, or not a PDF."""


class EmptyDocumentError(DocumentLoadError):
    """The file has no content or no pages."""


class NoExtractableTextError(DocumentLoadError):
    """Every page is empty after extraction (typically a scanned PDF)."""


class EmbeddingError(RagError):
    """Embedding model could not be loaded or returned invalid vectors."""


class VectorStoreError(RagError):
    """ChromaDB storage failed."""


class EmbeddingModelMismatchError(VectorStoreError):
    """The collection was built with a different embedding model."""


# ------------------------------------------------------------- data containers
@dataclass(frozen=True)
class PageText:
    """Cleaned text of one PDF page (1-based page number)."""

    page_number: int
    text: str


@dataclass(frozen=True)
class LoadedDocument:
    """A PDF after text extraction."""

    doc_id: str
    filename: str
    content_hash: str  # SHA-256 of the raw file bytes
    pages: tuple[PageText, ...]
    failed_pages: tuple[int, ...] = ()

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def pages_without_text(self) -> list[int]:
        return [p.page_number for p in self.pages if not p.text]


@dataclass
class Chunk:
    """One piece of text plus ChromaDB-compatible metadata."""

    chunk_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
