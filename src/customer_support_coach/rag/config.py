"""Configuration for the RAG module."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .chunker import validate_chunk_params
from .models import InvalidInputError

DEFAULT_PERSIST_DIRECTORY = Path("data") / "rag" / "chroma"
DEFAULT_COLLECTION_NAME = "support_docs"
DEFAULT_CHUNK_SIZE = 600
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 3
DEFAULT_EMBEDDING_PROVIDER = "onnx-minilm"


@dataclass(frozen=True)
class RagConfig:
    """Settings for :class:`RagPipeline`.

    ``persist_directory`` is relative to the current working directory,
    so run scripts from the repository root (or pass an absolute path).
    """

    persist_directory: Path = DEFAULT_PERSIST_DIRECTORY
    collection_name: str = DEFAULT_COLLECTION_NAME
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    default_top_k: int = DEFAULT_TOP_K
    embedding_provider: str = DEFAULT_EMBEDDING_PROVIDER
    embedding_model: str | None = None
    recursive: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "persist_directory", Path(self.persist_directory))
        validate_chunk_params(self.chunk_size, self.chunk_overlap)
        if (
            isinstance(self.default_top_k, bool)
            or not isinstance(self.default_top_k, int)
            or self.default_top_k < 1
        ):
            raise InvalidInputError("default_top_k must be a positive integer.")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "RagConfig":
        """Build a config from ``RAG_*`` environment variables.

        Supported: RAG_PERSIST_DIR, RAG_COLLECTION, RAG_CHUNK_SIZE,
        RAG_CHUNK_OVERLAP, RAG_TOP_K, RAG_EMBEDDING_PROVIDER,
        RAG_EMBEDDING_MODEL. Unset variables keep their defaults.
        """
        env = os.environ if environ is None else environ

        def _int(name: str, default: int) -> int:
            raw = env.get(name)
            if raw is None or raw == "":
                return default
            try:
                return int(raw)
            except ValueError:
                raise InvalidInputError(f"{name} must be an integer, got {raw!r}.") from None

        return cls(
            persist_directory=Path(env.get("RAG_PERSIST_DIR") or DEFAULT_PERSIST_DIRECTORY),
            collection_name=env.get("RAG_COLLECTION") or DEFAULT_COLLECTION_NAME,
            chunk_size=_int("RAG_CHUNK_SIZE", DEFAULT_CHUNK_SIZE),
            chunk_overlap=_int("RAG_CHUNK_OVERLAP", DEFAULT_CHUNK_OVERLAP),
            default_top_k=_int("RAG_TOP_K", DEFAULT_TOP_K),
            embedding_provider=env.get("RAG_EMBEDDING_PROVIDER") or DEFAULT_EMBEDDING_PROVIDER,
            embedding_model=env.get("RAG_EMBEDDING_MODEL") or None,
        )
