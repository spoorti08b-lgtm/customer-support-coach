"""Support Knowledge Base Ingestion and RAG Module.

Uses sentence-transformers ('all-MiniLM-L6-v2') and ChromaDB PersistentClient
to provide dense semantic retrieval over uploaded support documents.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import streamlit as st

from backend.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DIR,
    DATA_DIR,
    EMBEDDING_MODEL_NAME,
    EVAL_PATH,
    MAX_PDF_SIZE_BYTES,
    SAMPLE_PDFS_DIR,
)

COLLECTION_NAME = CHROMA_COLLECTION_NAME
MODEL_NAME = EMBEDDING_MODEL_NAME
MAX_FILE_SIZE_BYTES = MAX_PDF_SIZE_BYTES


@st.cache_resource(show_spinner=False)
def get_embedding_model() -> SentenceTransformer:
    """Load and cache the SentenceTransformer embedding model."""
    return SentenceTransformer(MODEL_NAME)


@st.cache_resource(show_spinner=False)
def get_chroma_client() -> chromadb.PersistentClient:
    """Load and cache the ChromaDB persistent client."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection():
    """Return the support_kb ChromaDB collection configured for cosine distance."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into windows of at most `size` characters with `overlap` characters.
    
    Preserves words where possible while respecting the maximum length.
    """
    clean_text = " ".join(text.split())
    if not clean_text:
        return []

    if len(clean_text) <= size:
        return [clean_text]

    step = max(1, size - overlap)
    chunks = []
    start = 0
    while start < len(clean_text):
        end = min(start + size, len(clean_text))
        chunk = clean_text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(clean_text):
            break
        start += step

    return chunks


def ingest_pdfs(files: list[Any]) -> dict[str, Any]:
    """Ingest multiple support PDFs, chunk, embed, and store in ChromaDB.
    
    Re-uploading the same PDF produces deterministic IDs based on file hash,
    updating existing records without creating duplicates.
    """
    collection = get_collection()
    model = get_embedding_model()

    added = 0
    ok_files: list[str] = []
    errors: list[str] = []

    for file in files:
        file_name = getattr(file, "name", "document.pdf")
        try:
            raw_bytes = file.getvalue() if hasattr(file, "getvalue") else file.read()
        except Exception as exc:
            errors.append(f"Failed to read '{file_name}': {exc}")
            continue

        if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
            errors.append(
                f"File '{file_name}' exceeds 20 MB limit ({len(raw_bytes) / (1024*1024):.1f} MB)."
            )
            continue

        file_hash = hashlib.sha256(raw_bytes).hexdigest()[:16]

        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
        except Exception as exc:
            errors.append(f"Could not parse '{file_name}' as PDF: {exc}")
            continue

        file_text_chunks: list[dict[str, Any]] = []

        for page_idx, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            page_chunks = chunk_text(page_text, size=500, overlap=50)

            for chunk_idx, chunk in enumerate(page_chunks):
                chunk_id = f"{file_hash}_p{page_idx}_c{chunk_idx}"
                file_text_chunks.append({
                    "id": chunk_id,
                    "text": chunk,
                    "metadata": {
                        "doc_name": file_name,
                        "source": file_name,
                        "page": page_idx,
                        "chunk_idx": chunk_idx,
                        "file_hash": file_hash,
                    },
                })

        if not file_text_chunks:
            errors.append(
                f"File '{file_name}' contains no extractable text. Scanned (image-only) PDFs are not supported."
            )
            continue

        ids = [item["id"] for item in file_text_chunks]
        documents = [item["text"] for item in file_text_chunks]
        metadatas = [item["metadata"] for item in file_text_chunks]

        embeddings = model.encode(documents).tolist()

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        added += len(file_text_chunks)
        ok_files.append(file_name)

    return {
        "added": added,
        "total": collection.count(),
        "files": ok_files,
        "errors": errors,
    }


def retrieve(query: str, k: int = 3) -> list[dict[str, Any]]:
    """Retrieve top-k chunks matching the query using cosine similarity."""
    clean_query = query.strip()
    if not clean_query:
        return []

    collection = get_collection()
    total = collection.count()
    if total == 0:
        return []

    model = get_embedding_model()
    query_embedding = model.encode([clean_query]).tolist()

    n_results = min(k, total)
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    raw_ids = results.get("ids")
    ids = raw_ids[0] if raw_ids and len(raw_ids) > 0 else []

    raw_docs = results.get("documents")
    documents = raw_docs[0] if raw_docs and len(raw_docs) > 0 else []

    raw_metas = results.get("metadatas")
    metadatas = raw_metas[0] if raw_metas and len(raw_metas) > 0 else []

    raw_dists = results.get("distances")
    distances = raw_dists[0] if raw_dists and len(raw_dists) > 0 else []

    hits = []
    n = min(len(documents), len(distances))
    for idx in range(n):
        doc = documents[idx]
        dist = distances[idx]
        meta = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
        chunk_id = ids[idx] if idx < len(ids) and ids[idx] else (meta.get("chunk_id") if meta else None)

        score = round(float(1.0 - dist), 4)
        doc_name = meta.get("doc_name", meta.get("source", "Unknown")) if meta else "Unknown"
        page = meta.get("page", 1) if meta else 1
        hits.append({
            "chunk_id": chunk_id,
            "text": doc,
            "doc_name": doc_name,
            "source": doc_name,
            "page": page,
            "score": score,
        })

    hits.sort(key=lambda hit: hit["score"], reverse=True)
    return hits[:k]


def stats() -> dict[str, Any]:
    """Return total chunk count and list of unique indexed document names."""
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return {"total": 0, "chunks": 0, "documents": [], "files": []}

    records = collection.get(include=["metadatas"])
    metas = records.get("metadatas", [])
    doc_names = sorted(list({
        m.get("doc_name")
        for m in metas
        if m and m.get("doc_name")
    }))

    return {
        "total": count,
        "chunks": count,
        "documents": doc_names,
        "files": doc_names,
    }


def get_doc_table_data() -> list[dict[str, Any]]:
    """Return detailed table of indexed documents: File, Pages count, Chunks count."""
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []

    records = collection.get(include=["metadatas"])
    metas = records.get("metadatas", [])

    doc_map: dict[str, dict[str, Any]] = {}
    for m in metas:
        if not m:
            continue
        doc = m.get("doc_name", "Unknown")
        page = m.get("page", 1)
        if doc not in doc_map:
            doc_map[doc] = {"pages": set(), "chunks": 0}
        doc_map[doc]["pages"].add(page)
        doc_map[doc]["chunks"] += 1

    rows = []
    for doc in sorted(doc_map.keys()):
        rows.append({
            "File": doc,
            "Pages": len(doc_map[doc]["pages"]),
            "Snippets": doc_map[doc]["chunks"],
            "Chunks": doc_map[doc]["chunks"],
        })
    return rows


def delete_document(doc_name: str) -> bool:
    """Delete all chunks for a specific document by file name."""
    collection = get_collection()
    try:
        collection.delete(where={"doc_name": doc_name})
        return True
    except Exception:
        return False


def load_sample_pdfs() -> dict[str, Any]:
    """Ingest every PDF in data/sample_pdfs/ skipping ones already indexed."""
    sample_dir = SAMPLE_PDFS_DIR
    if not sample_dir.exists():
        return {"added": 0, "skipped": 0, "files": []}

    current_docs = set(stats().get("documents", []))
    to_ingest = []
    skipped = []

    class DiskPdfFile:
        def __init__(self, p: Path):
            self.name = p.name
            self._data = p.read_bytes()

        def getvalue(self) -> bytes:
            return self._data

    for p in sorted(sample_dir.glob("*.pdf")):
        if p.name in current_docs:
            skipped.append(p.name)
        else:
            to_ingest.append(DiskPdfFile(p))

    if not to_ingest:
        return {"added": 0, "total": stats().get("chunks", 0), "skipped": len(skipped), "files": skipped, "errors": []}

    result = ingest_pdfs(to_ingest)
    result["skipped"] = len(skipped)
    return result


def evaluate_retrieval(k: int = 3) -> dict[str, Any]:
    """Evaluate retrieval accuracy on ground-truth evaluation dataset."""
    if not EVAL_PATH.exists():
        return {
            "total": 0,
            "hit_1": 0,
            "hit_3": 0,
            "hit_1_rate": 0.0,
            "hit_3_rate": 0.0,
            "misses": [],
            "items": [],
        }

    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        eval_set = json.load(f)

    hit1 = 0
    hit3 = 0
    misses = []
    items_out = []

    for item in eval_set:
        q = item["question"]
        exp_doc = item["expected_doc"]
        hits = retrieve(q, k=k)
        retrieved_docs = [h["doc_name"] for h in hits]

        is_hit1 = bool(retrieved_docs and retrieved_docs[0] == exp_doc)
        is_hit3 = bool(exp_doc in retrieved_docs)

        if is_hit1:
            hit1 += 1
        if is_hit3:
            hit3 += 1
        else:
            misses.append({
                "id": item.get("id", ""),
                "question": q,
                "expected_doc": exp_doc,
                "expected_page": item.get("expected_page", 1),
                "retrieved": ", ".join(retrieved_docs) if retrieved_docs else "None",
            })

        items_out.append({
            "question": q,
            "expected_doc": exp_doc,
            "top_doc": retrieved_docs[0] if retrieved_docs else "None",
            "top_score": hits[0]["score"] if hits else 0.0,
            "hit_1": is_hit1,
            "hit_3": is_hit3,
        })

    total = len(eval_set)
    return {
        "total": total,
        "hit_1": hit1,
        "hit_3": hit3,
        "hit_1_rate": round(hit1 / total, 4) if total > 0 else 0.0,
        "hit_3_rate": round(hit3 / total, 4) if total > 0 else 0.0,
        "misses": misses,
        "items": items_out,
    }


def clear() -> None:
    """Wipe the support_kb vector collection."""
    client = get_chroma_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
