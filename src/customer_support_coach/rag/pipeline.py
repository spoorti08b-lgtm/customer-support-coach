"""High-level RAG facade: ingest PDFs, search, inspect.

This is the only class other components need::

    from customer_support_coach.rag import RagPipeline
    rag = RagPipeline()
    rag.ingest_directory("docs/support_pdfs")
    context = rag.retrieve_context("How do I reset my password?")
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .chunker import TextChunker
from .config import RagConfig
from .document_loader import PdfDocumentLoader, make_doc_id
from .embeddings import EmbeddingProvider, create_embedder, validate_embeddings
from .models import InvalidInputError, RagError
from .retriever import RetrievalResult, Retriever
from .vector_store import ChromaVectorStore

INGESTED = "ingested"
UPDATED = "updated"
SKIPPED_UNCHANGED = "skipped_unchanged"
SKIPPED_DUPLICATE = "skipped_duplicate"
FAILED = "failed"


@dataclass
class IngestionResult:
    """Outcome for one PDF."""

    source: str
    filename: str
    status: str
    doc_id: str | None = None
    chunks_added: int = 0
    chunks_removed: int = 0
    pages_total: int = 0
    pages_without_text: list[int] = field(default_factory=list)
    message: str = ""
    error_type: str | None = None

    @property
    def ok(self) -> bool:
        return self.status != FAILED

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "ok": self.ok}


@dataclass
class IngestionReport:
    """Outcomes for a whole directory."""

    results: list[IngestionResult] = field(default_factory=list)

    def _by(self, *statuses: str) -> list[IngestionResult]:
        return [r for r in self.results if r.status in statuses]

    @property
    def succeeded(self) -> list[IngestionResult]:
        return self._by(INGESTED, UPDATED)

    @property
    def skipped(self) -> list[IngestionResult]:
        return self._by(SKIPPED_UNCHANGED, SKIPPED_DUPLICATE)

    @property
    def failed(self) -> list[IngestionResult]:
        return self._by(FAILED)

    @property
    def all_ok(self) -> bool:
        return not self.failed

    def summary(self) -> str:
        lines = [
            f"{len(self.results)} file(s): {len(self.succeeded)} ingested/updated, "
            f"{len(self.skipped)} skipped, {len(self.failed)} failed"
        ]
        lines += [f"  [{r.status}] {r.filename}: {r.message}" for r in self.results]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {"all_ok": self.all_ok, "results": [r.to_dict() for r in self.results]}


class RagPipeline:
    """Ingestion + retrieval behind four methods.

    ``ingest_pdf``, ``ingest_directory``, ``search``, ``get_collection_stats``.
    Collaborators can be injected (used by the unit tests).
    """

    def __init__(
        self,
        config: RagConfig | None = None,
        *,
        embedder: EmbeddingProvider | None = None,
        store: ChromaVectorStore | None = None,
        loader: PdfDocumentLoader | None = None,
        chunker: TextChunker | None = None,
    ):
        self.config = config or RagConfig()
        self.embedder = embedder or create_embedder(
            self.config.embedding_provider, self.config.embedding_model
        )
        self.loader = loader or PdfDocumentLoader()
        self.chunker = chunker or TextChunker(self.config.chunk_size, self.config.chunk_overlap)
        self.store = store or ChromaVectorStore(
            self.config.persist_directory,
            self.config.collection_name,
            embedding_model_name=self.embedder.name,
        )
        self.retriever = Retriever(self.embedder, self.store, self.config.default_top_k)

    # --------------------------------------------------------------- ingestion
    def ingest_pdf(self, path: str | Path) -> IngestionResult:
        """Ingest one PDF. Expected problems (missing/corrupt/scanned file,
        embedding or storage failure) are returned as ``status="failed"``
        rather than raised, so batch jobs keep going."""
        if isinstance(path, str) and path.strip():
            path = Path(path)
        if not isinstance(path, Path):
            raise InvalidInputError("path must be a non-empty string or Path.")
        try:
            return self._ingest(path)
        except RagError as exc:
            return IngestionResult(
                source=str(path),
                filename=path.name,
                status=FAILED,
                message=str(exc),
                error_type=type(exc).__name__,
            )

    def ingest_directory(self, directory: str | Path, recursive: bool | None = None) -> IngestionReport:
        """Ingest every PDF in a directory (raises if the directory is missing)."""
        flag = self.config.recursive if recursive is None else recursive
        report = IngestionReport()
        seen: dict[str, Path] = {}
        for file in self.loader.find_pdfs(directory, recursive=flag):
            doc_id = make_doc_id(file.name)
            if doc_id in seen:
                report.results.append(
                    IngestionResult(
                        source=str(file),
                        filename=file.name,
                        status=FAILED,
                        doc_id=doc_id,
                        message=f"Filename collides with {seen[doc_id]}; rename one of the files.",
                        error_type="FilenameCollision",
                    )
                )
                continue
            seen[doc_id] = file
            report.results.append(self.ingest_pdf(file))
        return report

    def _ingest(self, path: Path) -> IngestionResult:
        doc = self.loader.load(path)
        base = dict(
            source=str(path),
            filename=doc.filename,
            doc_id=doc.doc_id,
            pages_total=doc.page_count,
            pages_without_text=doc.pages_without_text,
        )
        existing = self.store.get_document_info(doc.doc_id)

        if existing and existing["content_hashes"] == {doc.content_hash}:
            counts = existing["chunk_counts"]
            if counts == {len(existing["chunk_ids"])}:
                return IngestionResult(
                    status=SKIPPED_UNCHANGED,
                    message="Content unchanged; nothing to do.",
                    **base,
                )

        twin = self.store.find_filename_by_hash(doc.content_hash, exclude_doc_id=doc.doc_id)
        if twin and not existing:
            return IngestionResult(
                status=SKIPPED_DUPLICATE,
                message=f"Identical content already ingested as {twin!r}.",
                **base,
            )

        chunks = self.chunker.chunk_document(doc)
        # Embed BEFORE touching the store so a failure leaves old data intact.
        vectors = validate_embeddings(
            self.embedder.embed_documents([c.text for c in chunks]), len(chunks)
        )
        stamp = datetime.now(timezone.utc).isoformat()
        for chunk in chunks:
            chunk.metadata["ingested_at"] = stamp

        self.store.upsert_chunks(chunks, vectors)
        new_ids = {c.chunk_id for c in chunks}
        stale = [i for i in (existing["chunk_ids"] if existing else []) if i not in new_ids]
        removed = self.store.delete_ids(stale)

        note = ""
        if base["pages_without_text"]:
            note = f" Pages without text: {base['pages_without_text']}."
        return IngestionResult(
            status=UPDATED if existing else INGESTED,
            chunks_added=len(chunks),
            chunks_removed=removed,
            message=f"{len(chunks)} chunk(s) stored.{note}",
            **base,
        )

    # --------------------------------------------------------------- retrieval
    def search(self, query: str, top_k: int | None = None) -> list[RetrievalResult]:
        """Top-k (default 3) most relevant chunks as :class:`RetrievalResult`."""
        return self.retriever.search(query, top_k)

    def retrieve_context(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Integration point for the Mock Agent / orchestrator.

        Same as :meth:`search` but returns JSON-safe dicts that can be placed
        directly in ``AgentResult.result`` or in an LLM prompt.
        """
        return [r.to_dict() for r in self.search(query, top_k)]

    # -------------------------------------------------------------- inspection
    def get_collection_stats(self) -> dict[str, Any]:
        return self.store.stats()

    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> "RagPipeline":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
