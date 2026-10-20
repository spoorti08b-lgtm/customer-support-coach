"""Top-k semantic retrieval over the vector store."""

from dataclasses import dataclass, field
from typing import Any

from .embeddings import EmbeddingProvider, validate_embeddings
from .models import InvalidInputError, InvalidQueryError
from .vector_store import ChromaVectorStore


@dataclass(frozen=True)
class RetrievalResult:
    """One retrieved chunk with everything needed for a citation.

    ``distance`` is exactly what ChromaDB returned for ``distance_metric``
    (lower = closer). For cosine collections ``cosine_similarity`` is derived
    as ``1 - distance``; it is ``None`` for other metrics.
    """

    rank: int
    chunk_id: str
    text: str
    source_filename: str | None
    page_start: int | None
    page_end: int | None
    chunk_index: int | None
    distance: float
    distance_metric: str
    doc_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def cosine_similarity(self) -> float | None:
        return 1.0 - self.distance if self.distance_metric == "cosine" else None

    @property
    def citation(self) -> str:
        """Human-readable source label, e.g. ``returns.pdf, p. 2``."""
        name = self.source_filename or "unknown source"
        if self.page_start is None:
            return name
        if self.page_end in (None, self.page_start):
            return f"{name}, p. {self.page_start}"
        return f"{name}, pp. {self.page_start}-{self.page_end}"

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict (works with ``AgentResult.result`` validation)."""
        return {
            "rank": self.rank,
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source_filename": self.source_filename,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "chunk_index": self.chunk_index,
            "distance": self.distance,
            "distance_metric": self.distance_metric,
            "cosine_similarity": self.cosine_similarity,
            "citation": self.citation,
            "doc_id": self.doc_id,
            "metadata": dict(self.metadata),
        }


class Retriever:
    """Embeds a question with the ingestion model and queries ChromaDB."""

    def __init__(
        self,
        embedder: EmbeddingProvider,
        store: ChromaVectorStore,
        default_top_k: int = 3,
        max_top_k: int = 50,
    ):
        self.embedder = embedder
        self.store = store
        self.default_top_k = default_top_k
        self.max_top_k = max_top_k

    def search(self, query: str, top_k: int | None = None) -> list[RetrievalResult]:
        """Return up to ``top_k`` (default 3) chunks, closest first.

        Returns ``[]`` for an empty collection. Raises ``InvalidQueryError``
        for a blank query, ``InvalidInputError`` for a bad ``top_k`` and
        ``EmbeddingError`` / ``VectorStoreError`` on backend failures.
        """
        if not isinstance(query, str) or not query.strip():
            raise InvalidQueryError("Query must be a non-empty string.")
        k = self.default_top_k if top_k is None else top_k
        if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= self.max_top_k:
            raise InvalidInputError(f"top_k must be an integer between 1 and {self.max_top_k}.")

        if self.store.count() == 0:
            return []

        vector = validate_embeddings([self.embedder.embed_query(query.strip())], 1)[0]
        rows = self.store.query(vector, k)[:k]

        results = []
        for rank, row in enumerate(rows, start=1):
            meta = row["metadata"]
            results.append(
                RetrievalResult(
                    rank=rank,
                    chunk_id=row["id"],
                    text=row["document"],
                    source_filename=meta.get("filename"),
                    page_start=meta.get("page_start"),
                    page_end=meta.get("page_end"),
                    chunk_index=meta.get("chunk_index"),
                    distance=row["distance"],
                    distance_metric=self.store.distance_metric,
                    doc_id=meta.get("doc_id"),
                    metadata=meta,
                )
            )
        return results
