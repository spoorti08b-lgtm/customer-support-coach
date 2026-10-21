"""Lightweight local RAG so the frontend works standalone.
TEAM INTEGRATION: replace ingest_pdfs() / retrieve() / stats() with the real RAG module
(keep the same return shapes and the UI won't change)."""
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
            return json.loads(KB.read_text())
        except json.JSONDecodeError:
            return []
    return []


def _save(idx):
    KB.parent.mkdir(parents=True, exist_ok=True)
    KB.write_text(json.dumps(idx))


def _tok(t):
    return re.findall(r"[a-z0-9]{3,}", t.lower())


def _chunk(text, size=120, overlap=20):
    words = text.split()
    step = size - overlap
    return [" ".join(words[i:i + size]) for i in range(0, len(words), step) if words[i:i + size]]


def ingest_pdfs(files):
    """files: list of Streamlit UploadedFile. Returns dict(added, total, files, errors)."""
    idx = _load()
    added, ok_files, errors = 0, [], []
    for f in files:
        try:
            reader = PdfReader(io.BytesIO(f.getvalue()))
            new = []
            for pno, page in enumerate(reader.pages, 1):
                for c in _chunk(page.extract_text() or ""):
                    new.append({"source": f.name, "page": pno, "text": c})
            if not new:
                errors.append(f"'{f.name}' has no readable text (scanned PDF?).")
                continue
            idx = [c for c in idx if c["source"] != f.name] + new  # re-upload replaces old chunks
            added += len(new)
            ok_files.append(f.name)
        except Exception:
            errors.append(f"'{f.name}' couldn't be read — is it a valid PDF?")
    _save(idx)
    return {"added": added, "total": len(idx), "files": ok_files, "errors": errors}


def stats():
    idx = _load()
    return {"total": len(idx), "files": sorted({c["source"] for c in idx})}


def clear():
    _save([])


def retrieve(query, k=3):
    idx = _load()
    if not idx:
        return []
    docs = [Counter(_tok(c["text"])) for c in idx]
    n = len(docs)
    df = Counter()
    for d in docs:
        df.update(d.keys())
    q = Counter(_tok(query))
    scored = []
    for c, d in zip(idx, docs):
        s = sum((1 + log(d[w])) * log(1 + n / df[w]) * q[w] for w in q if w in d)
        s /= sqrt(sum(d.values())) or 1
        if s > 0:
            scored.append({**c, "score": round(s, 3)})
    return sorted(scored, key=lambda x: -x["score"])[:k]
