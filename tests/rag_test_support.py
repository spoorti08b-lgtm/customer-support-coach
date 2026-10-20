"""Helpers for the RAG tests (no third-party dependencies).

* ``build_pdf``            - writes a small valid text PDF (pure Python).
* ``HashingTestEmbedder``  - deterministic bag-of-words vectors. TEST ONLY: it
                             stands in for the real model in unit tests.
"""

import hashlib
import math
import re
import sys
import textwrap
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _escape(line: str) -> str:
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(pages: list[str], wrap: int = 90) -> bytes:
    """Return PDF bytes; each item is one page (``""`` = page with no text,
    like a scanned page). ``pages=[]`` yields a PDF with zero pages."""
    objects: dict[int, bytes] = {}
    n = len(pages)
    page_ids = [4 + 2 * i for i in range(n)]
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode()
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for i, text in enumerate(pages):
        lines = []
        for para in text.split("\n"):
            lines.extend(textwrap.wrap(para, wrap) or [""])
        assert len(lines) <= 50, "page text too long for the test PDF writer"
        body = ["BT", "/F1 11 Tf", "14 TL", "50 750 Td"]
        for l in lines:
            body.append(f"({_escape(l)}) '")
        body.append("ET")
        stream = ("\n".join(body) if text.strip() else "").encode("latin-1", "replace")
        pid, cid = page_ids[i], page_ids[i] + 1
        objects[pid] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {cid} 0 R >>"
        ).encode()
        objects[cid] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += b"%d 0 obj\n" % num + objects[num] + b"\nendobj\n"
    xref = len(out)
    size = max(objects) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    for num in range(1, size):
        out += b"%010d 00000 n \n" % offsets[num]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    return bytes(out)


def write_pdf(path: Path, pages: list[str]) -> Path:
    path.write_bytes(build_pdf(pages))
    return path


class HashingTestEmbedder:
    """Deterministic 64-dim hashed bag-of-words embedder (unit tests only)."""

    name = "test-hashing-embedder"
    DIM = 64

    def __init__(self):
        self.document_calls = 0
        self.query_calls = 0

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.DIM
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts):
        self.document_calls += 1
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        self.query_calls += 1
        return self._vec(text)


class FailingEmbedder(HashingTestEmbedder):
    """Raises EmbeddingError on every call."""

    def embed_documents(self, texts):
        from customer_support_coach.rag import EmbeddingError

        raise EmbeddingError("simulated embedding failure")

    embed_query = embed_documents
