"""Lightweight local RAG so the frontend works standalone.

TEAM INTEGRATION: replace ingest_pdfs(), retrieve(), and stats() with the real
RAG module while keeping the same return shapes.
"""
import io
import json
import re
from collections import Counter
from math import log, sqrt
from pathlib import Path

from pypdf import PdfReader

KB = Path(__file__).resolve().parent.parent / "data" / "kb_index.json"


def _load():
    if KB.exists():
        try:
            return json.loads(KB.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def _save(idx):
    KB.parent.mkdir(parents=True, exist_ok=True)
    KB.write_text(json.dumps(idx), encoding="utf-8")


def _tok(text):
    return re.findall(r"[a-z0-9]{3,}", text.lower())


def _chunk(text, size=120, overlap=20):
    words = text.split()
    step = size - overlap
    return [
        " ".join(words[i:i + size])
        for i in range(0, len(words), step)
        if words[i:i + size]
    ]


def ingest_pdfs(files):
    """Read uploaded PDFs and return added, total, files, and errors."""
    idx = _load()
    added = 0
    ok_files = []
    errors = []

    for file in files:
        try:
            reader = PdfReader(io.BytesIO(file.getvalue()))
            new_chunks = []

            for page_number, page in enumerate(reader.pages, 1):
                page_text = page.extract_text() or ""
                for chunk in _chunk(page_text):
                    new_chunks.append({
                        "source": file.name,
                        "page": page_number,
                        "text": chunk,
                    })

            if not new_chunks:
                errors.append(
                    f"'{file.name}' has no readable text (scanned PDF?)."
                )
                continue

            # Re-uploading a file replaces its previous chunks.
            idx = [chunk for chunk in idx if chunk["source"] != file.name]
            idx.extend(new_chunks)
            added += len(new_chunks)
            ok_files.append(file.name)

        except Exception:
            errors.append(
                f"'{file.name}' couldn't be read — is it a valid PDF?"
            )

    _save(idx)
    return {
        "added": added,
        "total": len(idx),
        "files": ok_files,
        "errors": errors,
    }


def stats():
    """Return the total number of chunks and indexed source files."""
    idx = _load()
    return {
        "total": len(idx),
        "files": sorted({chunk["source"] for chunk in idx}),
    }


def clear():
    """Remove all indexed knowledge chunks."""
    _save([])


def retrieve(query, k=3):
    """Return the top matching knowledge chunks for a query."""
    idx = _load()
    if not idx:
        return []

    documents = [Counter(_tok(chunk["text"])) for chunk in idx]
    document_count = len(documents)
    document_frequency = Counter()

    for document in documents:
        document_frequency.update(document.keys())

    query_words = Counter(_tok(query))
    scored = []

    for chunk, document in zip(idx, documents):
        score = sum(
            (1 + log(document[word]))
            * log(1 + document_count / document_frequency[word])
            * query_words[word]
            for word in query_words
            if word in document
        )
        score /= sqrt(sum(document.values())) or 1

        if score > 0:
            scored.append({**chunk, "score": round(score, 3)})

    return sorted(scored, key=lambda item: -item["score"])[:k]
