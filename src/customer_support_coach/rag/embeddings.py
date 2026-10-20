"""Embedding providers.

Every provider exposes:

* ``name``            - identifier stored with the collection so ingestion and
                        querying are guaranteed to use the same model;
* ``embed_documents`` - list[str] -> list[list[float]]
* ``embed_query``     - str -> list[float]

Default: Chroma's bundled ONNX build of ``all-MiniLM-L6-v2`` (384 dims, runs on
CPU with ``onnxruntime``; ~80 MB downloaded once to ``~/.cache/chroma``).
"""

import math
from typing import Protocol, Sequence, runtime_checkable

from .models import EmbeddingError, InvalidInputError


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def validate_texts(texts: Sequence[str]) -> list[str]:
    """Reject empty input or non-string / blank items."""
    if isinstance(texts, str) or not isinstance(texts, Sequence) or len(texts) == 0:
        raise EmbeddingError("Expected a non-empty list of strings to embed.")
    for i, item in enumerate(texts):
        if not isinstance(item, str) or not item.strip():
            raise EmbeddingError(f"Text at position {i} is empty or not a string.")
    return list(texts)


def validate_embeddings(vectors: object, expected_count: int) -> list[list[float]]:
    """Check count, equal non-zero dimension and finite numbers."""
    if not isinstance(vectors, (list, tuple)) or len(vectors) != expected_count:
        raise EmbeddingError(
            f"Embedder returned {len(vectors) if hasattr(vectors, '__len__') else '?'} "
            f"vectors for {expected_count} texts."
        )
    cleaned: list[list[float]] = []
    dimension = None
    for i, vec in enumerate(vectors):
        try:
            row = [float(x) for x in vec]
        except (TypeError, ValueError):
            raise EmbeddingError(f"Embedding {i} is not a numeric vector.") from None
        if not row or any(not math.isfinite(x) for x in row):
            raise EmbeddingError(f"Embedding {i} is empty or contains NaN/inf.")
        if dimension is None:
            dimension = len(row)
        elif len(row) != dimension:
            raise EmbeddingError("Embeddings have inconsistent dimensions.")
        cleaned.append(row)
    return cleaned


class OnnxMiniLMEmbedder:
    """all-MiniLM-L6-v2 through Chroma's ONNX runtime wrapper (default)."""

    name = "onnx-all-MiniLM-L6-v2"

    def __init__(self, batch_size: int = 32):
        if batch_size < 1:
            raise InvalidInputError("batch_size must be positive.")
        self.batch_size = batch_size
        self._fn = None

    def _function(self):
        if self._fn is None:
            try:
                from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

                self._fn = ONNXMiniLM_L6_V2()
            except Exception as exc:
                raise EmbeddingError(f"Cannot initialise the ONNX embedding model: {exc}") from exc
        return self._fn

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        items = validate_texts(texts)
        fn = self._function()
        out: list[list[float]] = []
        try:
            for i in range(0, len(items), self.batch_size):
                batch = items[i : i + self.batch_size]
                out.extend([[float(x) for x in vec] for vec in fn(batch)])
        except Exception as exc:  # first call downloads the model: network errors land here
            raise EmbeddingError(
                f"Embedding failed ({type(exc).__name__}: {exc}). On first use the model "
                "(~80 MB) is downloaded to ~/.cache/chroma; check your internet connection."
            ) from exc
        return validate_embeddings(out, len(items))

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class SentenceTransformerEmbedder:
    """Optional provider using the ``sentence-transformers`` package.

    Not installed by default (it pulls in PyTorch). Install it yourself and
    set ``embedding_provider="sentence-transformers"``.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", batch_size: int = 32):
        self.model_name = model_name
        self.batch_size = batch_size
        self.name = f"sentence-transformers:{model_name}"
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingError(
                    "sentence-transformers is not installed (pip install sentence-transformers)."
                ) from exc
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:
                raise EmbeddingError(f"Cannot load model {self.model_name!r}: {exc}") from exc
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        items = validate_texts(texts)
        model = self._load()
        try:
            vectors = model.encode(
                items,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingError(f"Embedding failed: {exc}") from exc
        return validate_embeddings([list(v) for v in vectors], len(items))

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def create_embedder(provider: str = "onnx-minilm", model_name: str | None = None) -> EmbeddingProvider:
    """Factory used by :class:`RagPipeline`. Add new providers here."""
    key = (provider or "").strip().lower()
    if key == "onnx-minilm":
        if model_name not in (None, "", "all-MiniLM-L6-v2"):
            raise InvalidInputError("The 'onnx-minilm' provider only supports all-MiniLM-L6-v2.")
        return OnnxMiniLMEmbedder()
    if key == "sentence-transformers":
        return SentenceTransformerEmbedder(model_name) if model_name else SentenceTransformerEmbedder()
    raise InvalidInputError(
        f"Unknown embedding provider {provider!r}. Use 'onnx-minilm' or 'sentence-transformers'."
    )
