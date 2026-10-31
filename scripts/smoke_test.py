"""Smoke test: verifies imports, RAG ingestion, ChromaDB vector retrieval,

session persistence, and orchestrator workflow execution.

Run from project root:
    python smoke_test.py
"""

from __future__ import annotations

import pathlib
import sys

# Force UTF-8 output on Windows to avoid codec errors
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Bootstrap repository root into sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

print("1. Checking module imports...")
from backend.config import SAMPLE_PDFS_DIR
from backend.core.data_models import InteractionMode, Session
from backend.orchestrator import run_workflow, WorkflowRequest, WorkflowResponse
from backend.orchestrator.mock_components import MockAgent, MockSessionManager
from backend.services import pipeline_stub, rag_stub, storage, validation
from frontend.views import architecture, console, report, sessions, setup

print("   [OK] All modules imported successfully.")

# ── Test RAG ingestion + retrieval ─────────────────────────────────────────

class FakePdf:
    """Mimics a Streamlit UploadedFile object."""

    def __init__(self, path: pathlib.Path | str) -> None:
        p = pathlib.Path(path)
        self.name = p.name
        self._data = p.read_bytes()

    def getvalue(self) -> bytes:
        return self._data


sample_dir = SAMPLE_PDFS_DIR
pdf_paths = sorted(sample_dir.glob("*.pdf"))
pdf_files = [FakePdf(p) for p in pdf_paths]

print(f"\n2. Ingesting {len(pdf_files)} sample PDFs into ChromaDB...")
rag_stub.clear()
result = rag_stub.ingest_pdfs(pdf_files)
print(f"   Added chunks : {result['added']}")
print(f"   Total in KB  : {result['total']}")
print(f"   Files        : {result['files']}")
print(f"   Errors       : {result['errors']}")

assert result["added"] > 0, "No chunks were ingested!"
assert result["errors"] == [], f"Ingestion errors encountered: {result['errors']}"
print("   [OK] Ingestion and embedding OK.")

# ── Test vector retrieval ──────────────────────────────────────────────────

query = "What is the refund window?"
chunks = rag_stub.retrieve(query, k=3)
print(f"\n3. Retrieving query: {query!r}")
print(f"   {len(chunks)} chunk(s) returned:")
for i, c in enumerate(chunks, 1):
    print(f"   #{i} doc={c['doc_name']} | page={c['page']} | score={c['score']:.4f}")
    print(f"        text preview: {c['text'][:80]}...")

assert len(chunks) > 0, "No chunks returned from retrieval!"
assert all("doc_name" in c for c in chunks), "Chunks missing 'doc_name' field!"
assert all("score" in c for c in chunks), "Chunks missing 'score' field!"
assert all("page" in c for c in chunks), "Chunks missing 'page' field!"
print("   [OK] ChromaDB retrieval OK -- source filenames and cosine scores confirmed.")

# ── Test session save ──────────────────────────────────────────────────────

print("\n4. Testing session persistence (data/sessions/)...")
session_id = storage.new_id()
test_session = Session(
    session_id=session_id,
    mode=InteractionMode.SIMULATOR,
    product_context={"product": "Smoke Test Device"},
    scenario="Customer has a setup inquiry during automated smoke test.",
)

saved_id = storage.save(test_session)
assert saved_id == session_id, "Saved ID does not match session ID"
saved_file = storage.DIR / f"{session_id}.json"
assert saved_file.exists(), f"Session JSON file {saved_file} was not written to disk!"

loaded_data = storage.load(session_id)
assert loaded_data is not None, "Failed to reload session data"
assert loaded_data.get("session_id") == session_id

# Clean up test session file
deleted = storage.delete_session(session_id)
assert deleted, "Failed to clean up test session"
assert not saved_file.exists()
print("   [OK] Session save, load, and delete verified.")

# ── Test orchestrator ───────────────────────────────────────────────────────

print("\n5. Running orchestrator workflow...")
sm = MockSessionManager()
agent = MockAgent()
request = WorkflowRequest(session_id="sess-demo01", message="Where is my order?")
response = run_workflow(request, sm, agent)
print(f"   Status      : {response.status}")
print(f"   Result keys : {list(response.result.keys()) if response.result else None}")
assert response.status == "completed"
assert response.result
print("   [OK] Orchestrator workflow execution OK.")

# ── Clean up ────────────────────────────────────────────────────────────────
rag_stub.clear()
print("\n[PASS] All smoke tests passed successfully.")
