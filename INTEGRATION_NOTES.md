# RAG Pipeline — Integration Notes

Task: RAG Pipeline and Document Ingestion (PDF extraction, chunking, embeddings, ChromaDB, top-3 retrieval)
Project: AI Customer Support Coaching Assistant · Infosys Springboard Virtual Internship 7.0

## Existing files modified: NONE

`data_models.py`, `database.py`, `session_manager.py`, `src/customer_support_coach/__init__.py`,
`README.md`, `.gitignore`, and all existing tests are untouched. Importing the RAG module is
`from customer_support_coach.rag import RagPipeline`; no change to the package `__init__` is needed.

## New files (26)

```
src/customer_support_coach/rag/__init__.py
src/customer_support_coach/rag/models.py            (extra file: exceptions + data containers)
src/customer_support_coach/rag/config.py            (extra file: RagConfig)
src/customer_support_coach/rag/document_loader.py
src/customer_support_coach/rag/chunker.py
src/customer_support_coach/rag/embeddings.py
src/customer_support_coach/rag/vector_store.py
src/customer_support_coach/rag/retriever.py
src/customer_support_coach/rag/pipeline.py
tests/rag_test_support.py                           (test-only PDF writer + hashing embedder)
tests/test_document_loader.py
tests/test_chunker.py
tests/test_vector_store.py
tests/test_retriever.py
tests/test_rag_pipeline.py
tests/test_rag_smoke_real_embeddings.py             (skipped unless RAG_SMOKE=1)
docs/rag_pipeline.md
examples/rag_demo.py
examples/make_sample_pdfs.py
examples/sample_docs/account_and_password_faq.pdf   (synthetic, invented company)
examples/sample_docs/returns_and_refunds.pdf
examples/sample_docs/shipping_and_delivery.pdf
data/rag/.gitignore                                 (keeps ChromaDB files out of Git)
requirements-rag.txt
INTEGRATION_NOTES.md
GITHUB_INTEGRATION.md
```

## Deviations from the requested structure (and why)

1. **`models.py` and `config.py` added** inside `rag/`: shared exceptions/dataclasses and one settings
   object, so the seven requested modules do not import each other in circles.
2. **Root `README.md` and `.gitignore` are not shipped.** `README.md` is a one-line stub that
   teammates may edit, and `.gitignore` exists only on the `feature/data-model-validation` branch.
   Shipping either would cause merge conflicts. Instead `data/rag/.gitignore` ignores generated
   vector data, and `GITHUB_INTEGRATION.md` shows how to ignore `__pycache__`/`.venv` locally.
   A README snippet you can paste is at the bottom of this file.
3. **`tests/rag_test_support.py`** is an extra helper (not a test); `test_rag_smoke_real_embeddings.py`
   is the separate smoke test requested.
4. **No `tests/__init__.py`**: not present on the session-manager branch; the new tests insert
   `src` on `sys.path` themselves, so they run with or without it.

## What was found in the repository

* `main` currently holds only `README.md` (1 commit). The shared code lives on unmerged branches:
  `feature/data-model-validation` (models, `docs/data_contract.md`, `.gitignore`, `tests/__init__.py`)
  and `feature/session-manager` (commit `6324fda`: adds `database.py`, `session_manager.py`, tests).
  `feature/mock-agent`, `feature/orchestrator`, `feature/streamlit-ui`, `feature/testing` and
  `chore/project-setup` contain only the initial README.
* Test framework: **`unittest`** (no pytest). Style: classes `TestXxx(unittest.TestCase)`, temp dirs.
  The new tests follow it.
* No dependency file exists anywhere; Python 3.10+ is implied by `dict[str, Any] | None` annotations.
  `requirements-rag.txt` is new and does not alter any project-wide setup.
* No agent/orchestrator interface exists yet, so the downstream contract is **documented as an
  assumption** (`docs/rag_pipeline.md`, section 8): `RagPipeline.retrieve_context(query, top_k=3)`
  returns JSON-safe dicts.
* **Works on any base**: `rag` has no imports from other project modules, so it works on `main`
  (where `customer_support_coach/__init__.py` does not exist yet, Python treats it as a namespace
  package) and keeps working after the other branches merge. The one test that validates results against
  `AgentResult` is skipped automatically when `data_models.py` is absent.
* Existing `SessionManager` uses `data/customer_support.db`; the RAG default store is `data/rag/chroma`.
  They do not overlap. Note that the shared SQLite file is not git-ignored on any branch; consider
  asking the team to ignore `data/*.db`.

## Interface summary

```python
from customer_support_coach.rag import RagPipeline
rag = RagPipeline()
rag.ingest_pdf(path) / rag.ingest_directory(path)   # -> IngestionResult / IngestionReport
rag.search(query, top_k=3)                           # -> list[RetrievalResult]
rag.retrieve_context(query, top_k=3)                 # -> list[dict]  (for Mock Agent / orchestrator)
rag.get_collection_stats()                           # -> dict
```

## Optional README snippet

```markdown
## RAG pipeline
PDF ingestion, chunking, embeddings and top-3 retrieval live in `src/customer_support_coach/rag`.
Install: `py -m pip install -r requirements-rag.txt`. Docs: `docs/rag_pipeline.md`.
Tests: `$env:PYTHONPATH="src"; py -m unittest discover -s tests`.
```
