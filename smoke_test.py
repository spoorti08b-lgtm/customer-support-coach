"""
Smoke test: verifies all imports work and the RAG pipeline ingests
the sample PDFs and retrieves real chunks with source filenames.

Run from the project root:
    py -3 smoke_test.py
"""
import pathlib
import sys

# Force UTF-8 output on Windows to avoid codec errors
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

print("Checking imports...")

from orchestrator import run_workflow, WorkflowRequest, WorkflowResponse
from orchestrator.mock_components import MockAgent, MockSessionManager
from utils import storage, rag_stub, validation, pipeline_stub
from views import setup, console, report

print("  [OK] All imports OK")

# ── Test RAG ingestion + retrieval ─────────────────────────────────────────

class FakePdf:
    """Mimics a Streamlit UploadedFile object."""
    def __init__(self, path):
        p = pathlib.Path(path)
        self.name = p.name
        self._data = p.read_bytes()

    def getvalue(self):
        return self._data


sample_dir = pathlib.Path("data/sample_pdfs")
pdf_files = [FakePdf(p) for p in sorted(sample_dir.glob("*.pdf"))]

print(f"\nIngesting {len(pdf_files)} sample PDFs...")
result = rag_stub.ingest_pdfs(pdf_files)
print(f"  added   : {result['added']} chunks")
print(f"  total   : {result['total']} chunks in knowledge base")
print(f"  files   : {result['files']}")
print(f"  errors  : {result['errors']}")

assert result["added"] > 0, "No chunks were ingested!"
assert result["errors"] == [], f"Ingestion errors: {result['errors']}"
print("  [OK] Ingestion OK")

# ── Test retrieval ──────────────────────────────────────────────────────────

query = "how do I reset my password"
chunks = rag_stub.retrieve(query, k=3)
print(f"\nRetrieval for: {query!r}")
print(f"  {len(chunks)} chunk(s) returned:")
for i, c in enumerate(chunks, 1):
    print(f"  #{i} source={c['source']}  page={c['page']}  score={c['score']}")
    print(f"       text preview: {c['text'][:80]}...")

assert len(chunks) > 0, "No chunks returned from retrieval!"
assert all("source" in c for c in chunks), "Chunks missing 'source' field!"
assert all("score" in c for c in chunks), "Chunks missing 'score' field!"
print("  [OK] Retrieval OK -- source filenames confirmed")

# ── Test orchestrator ───────────────────────────────────────────────────────

print("\nRunning orchestrator workflow...")
sm = MockSessionManager()
agent = MockAgent()
request = WorkflowRequest(session_id="sess-demo01", message="Where is my order?")
response = run_workflow(request, sm, agent)
print(f"  status  : {response.status}")
print(f"  result keys: {list(response.result.keys()) if response.result else None}")
assert response.status == "completed"
assert response.result
print("  [OK] Orchestrator workflow OK")

# ── Clean up ────────────────────────────────────────────────────────────────
rag_stub.clear()
print("\n[PASS] All smoke tests passed.")
