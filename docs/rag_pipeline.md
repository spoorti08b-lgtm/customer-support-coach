# RAG Pipeline — PDF Ingestion, Embeddings, ChromaDB, Top-3 Retrieval

Module: `src/customer_support_coach/rag/` · Project: AI Customer Support Coaching Assistant
(Infosys Springboard Virtual Internship 7.0)

The module turns support PDFs into searchable chunks and returns the **3 most relevant chunks,
with file name and page numbers**, for a customer question. It does not generate answers and does
not touch SQLite sessions.

## 1. Architecture and data flow

```
PDF files ──► PdfDocumentLoader ──► TextChunker ──► EmbeddingProvider ──► ChromaVectorStore
 (folder)      page text, SHA-256     chunks +        384-d vectors         persistent collection
               cleaning, errors       page ranges     (MiniLM, local)       "support_docs"
                                                                                  ▲
question ─────────────────────────► EmbeddingProvider ──► Retriever ──────────────┘
                                     (same model)         top-k + citations ──► Mock Agent / orchestrator
```

| File | Responsibility |
|---|---|
| `models.py` | exceptions, `PageText`, `LoadedDocument`, `Chunk` |
| `config.py` | `RagConfig` (defaults, `from_env()`) |
| `document_loader.py` | find PDFs, extract text per page (pypdf), clean whitespace, hash, doc id |
| `chunker.py` | boundary-aware chunks with page range metadata |
| `embeddings.py` | provider interface, ONNX MiniLM (default), optional sentence-transformers |
| `vector_store.py` | ChromaDB persistent collection (upsert, delete, query, stats) |
| `retriever.py` | `Retriever`, `RetrievalResult` |
| `pipeline.py` | `RagPipeline` facade, `IngestionResult`, `IngestionReport` |

## 2. Installation (Windows / PowerShell)

```powershell
cd path\to\customer-support-coach
py -3.12 -m venv .venv            # Python 3.10+ works; 3.12 is what was tested
.\.venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope Process Bypass
py -m pip install --upgrade pip
py -m pip install -r requirements-rag.txt
$env:PYTHONPATH = "src"           # lets Python find customer_support_coach
```

`PYTHONPATH` must be set in every new PowerShell window (or run `py -m pip install -e .` if your
team adds packaging later). No Docker, no API keys, no paid services.

## 3. Embedding model

* Default provider `onnx-minilm`: **all-MiniLM-L6-v2**, 384 dimensions, run through ChromaDB's
  bundled ONNX wrapper on CPU. No PyTorch needed.
* **First use downloads ~80 MB** to `%USERPROFILE%\.cache\chroma\onnx_models`. After that it works
  offline. If the download fails you get an `EmbeddingError` explaining it; ingestion then reports
  `failed` and the store is not modified.
* The model name is saved in the collection metadata. Opening the collection with a different
  model raises `EmbeddingModelMismatchError`, so ingestion and querying cannot silently diverge.
* Switching model: set `RagConfig(embedding_provider="sentence-transformers",
  embedding_model="sentence-transformers/all-MiniLM-L6-v2")` after `pip install sentence-transformers`,
  or add a class with `name`, `embed_documents`, `embed_query` and register it in
  `create_embedder()`. **Use a new `collection_name` or `persist_directory` when changing models.**
  (The sentence-transformers provider was written but not run in the development sandbox.)
* The model reads about 256 tokens (~1000 characters) per chunk; longer text is truncated by the
  model, which is one reason chunks are kept at 600 characters.

## 4. PDF ingestion workflow

For each file (`ingest_pdf`) the pipeline:

1. Loads it: checks the file exists and is a `.pdf`, reads bytes, computes a **SHA-256 content hash**.
2. Extracts text page by page (page numbers are 1-based), then cleans it: control characters
   removed, runs of spaces collapsed, line ends unified, 3+ blank lines reduced to one. Hyphens,
   punctuation and numbers are untouched.
3. Checks the store: same file name with the same hash and all chunks present → `skipped_unchanged`
   (no embedding work). Different name but identical content → `skipped_duplicate`.
4. Chunks, embeds (**before** writing anything), upserts the new chunks, then deletes only that
   document's stale chunks. Other documents are never touched.

Document identity = **file name** (case-insensitive), so an edited file with the same name replaces
its old chunks. Two different folders containing the same file name are reported as
`FilenameCollision` during a recursive scan; rename one.

Outcomes (`IngestionResult.status`): `ingested`, `updated`, `skipped_unchanged`,
`skipped_duplicate`, `failed` (with `error_type` and `message`). `ingest_pdf` does not raise for
expected problems, so one bad file cannot stop a batch:

| Situation | Result |
|---|---|
| file missing | `failed` / `DocumentNotFoundError` |
| corrupted, encrypted, or not a PDF | `failed` / `UnreadableDocumentError` |
| 0 bytes or 0 pages | `failed` / `EmptyDocumentError` |
| **scanned PDF, no text on any page** | `failed` / `NoExtractableTextError` (not counted as ingested) |
| some blank pages | succeeds; `pages_without_text` lists them |
| embedding or storage failure | `failed` / `EmbeddingError` or `VectorStoreError` |

## 5. Chunking defaults

| Setting | Default | Why |
|---|---|---|
| `chunk_size` | **600 characters** (~110–150 words) | FAQ answers and manual steps are typically a paragraph; this fits comfortably under the model's ~256-token limit and keeps one chunk about one topic. |
| `chunk_overlap` | **100 characters** (~17%) | Keeps a sentence that straddles a boundary retrievable from either side, without much duplicated storage. |

Chunks end at the best boundary in the second half of the window (paragraph, line, sentence,
word, in that order). Chunk ids are deterministic: `<doc_id>:c00000`, `<doc_id>:c00001`, ….
These defaults were chosen by reasoning about the content type, **not tuned on real support
manuals**; check retrieval quality on your own documents and adjust via `RagConfig` or the
`RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` environment variables.

Metadata stored per chunk (all ChromaDB-compatible scalars): `doc_id`, `filename`, `page_start`,
`page_end`, `chunk_index`, `chunk_count`, `char_start`, `char_end`, `content_hash`,
`ingested_at` (UTC ISO time), `embedding_model`.

## 6. ChromaDB persistence

* Default path `data/rag/chroma` (relative to the working directory — run from the repo root),
  collection `support_docs`, cosine distance. Change with `RagConfig(persist_directory=...,
  collection_name=...)` or `RAG_PERSIST_DIR` / `RAG_COLLECTION`.
* The ZIP includes `data/rag/.gitignore` (ignores everything in `data/rag/` except itself), so
  vector databases never reach Git.
* Call `rag.close()` (or use `with RagPipeline(...) as rag:`) when finished; this releases
  file handles, which matters for deleting folders on Windows.
* Tested against chromadb 1.5.9 using `PersistentClient`, `get_or_create_collection(configuration=
  {"hnsw": {"space": "cosine"}}, embedding_function=None)`, `upsert`, `query`, `get`, `delete`.
  Embeddings are always passed in explicitly.

## 7. Usage

```python
from customer_support_coach.rag import RagPipeline, RagConfig

rag = RagPipeline()                                   # or RagPipeline(RagConfig(...))
report = rag.ingest_directory("docs/support_pdfs")    # whole folder
print(report.summary())
result = rag.ingest_pdf("docs/support_pdfs/returns.pdf")   # one file
print(result.status, result.message)

hits = rag.search("How do I reset my password?")      # top 3 by default
for h in hits:
    print(h.rank, h.citation, h.distance, h.text[:80])

print(rag.get_collection_stats())
rag.close()
```

Public methods on `RagPipeline`:

| Method | Returns |
|---|---|
| `ingest_pdf(path)` | `IngestionResult` |
| `ingest_directory(path, recursive=None)` | `IngestionReport` (`.succeeded`, `.skipped`, `.failed`, `.all_ok`, `.summary()`) |
| `search(query, top_k=None)` | `list[RetrievalResult]` (best first, never more than `top_k`) |
| `retrieve_context(query, top_k=None)` | `list[dict]` (JSON-safe; for agents) |
| `get_collection_stats()` | dict: totals plus per-document chunk counts |

`search` returns `[]` for an empty collection, fewer than `top_k` when fewer chunks exist, raises
`InvalidQueryError` for a blank query and `InvalidInputError` for a bad `top_k`.

### Result structure

```json
{
  "rank": 1,
  "chunk_id": "doc-account-and-password-faq-1a2b3c4d5e:c00000",
  "text": "How do I reset my password? Open the sign-in page ...",
  "source_filename": "account_and_password_faq.pdf",
  "page_start": 1, "page_end": 1, "chunk_index": 0,
  "distance": 0.31, "distance_metric": "cosine",
  "cosine_similarity": 0.69,
  "citation": "account_and_password_faq.pdf, p. 1",
  "doc_id": "doc-account-and-password-faq-1a2b3c4d5e",
  "metadata": {"filename": "...", "content_hash": "...", "embedding_model": "onnx-all-MiniLM-L6-v2"}
}
```

(Illustrative values.) `distance` is exactly what ChromaDB returns; **lower is closer**.
`cosine_similarity` is derived as `1 - distance`, present only for cosine collections.

## 8. Using it from the Mock Agent / orchestrator

The orchestrator only needs a query string and gets structured chunks back:

```python
from customer_support_coach.rag import RagPipeline, InvalidQueryError, RagError

rag = RagPipeline()          # create once, reuse

def get_support_context(customer_message: str) -> list[dict]:
    try:
        return rag.retrieve_context(customer_message, top_k=3)
    except InvalidQueryError:
        return []            # blank message
    except RagError as exc:
        # embedding/storage problem: continue without documentation
        return []

context = get_support_context("My parcel has not arrived")
# each item: text, citation, source_filename, page_start/page_end, distance, ...
```

Because `to_dict()` output is strict-JSON-safe, it can be stored directly with the shared models:
`AgentResult(session_id=..., agent_type="rag", result={"retrieved_context": context})`
(covered by a unit test when `data_models.py` is present). **Assumption:** no agent interface is
defined yet in the repository (the `feature/mock-agent` and `feature/orchestrator` branches only
contain the README), so this call shape is a proposal for the teammates to adopt or adjust. The
RAG module imports nothing from `database.py` or `session_manager.py`.

## 9. Known limitations

* **No OCR.** Scanned/image-only PDFs are rejected with a clear error (`NoExtractableTextError`);
  they are never counted as ingested. Pages without text inside an otherwise normal PDF are skipped
  and listed in `pages_without_text`.
* Text extraction quality depends on the PDF. Multi-column layouts, tables and headers/footers may
  produce jumbled or repeated text (pypdf extracts text in stream order).
* Document identity is the file name; same-named files in different folders collide.
* Deleting a PDF from the folder does not remove it from the store. Use
  `rag.store.delete_document(doc_id)` (ids appear in `get_collection_stats()`).
* The embedding model is English-centric.
* One process at a time should write to a given persist directory.
* Retrieval quality with the real model was **not** measured on real support manuals.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: customer_support_coach` | `$env:PYTHONPATH = "src"` from the repo root. |
| `ModuleNotFoundError: chromadb` / `pypdf` | Activate the venv, then `py -m pip install -r requirements-rag.txt`. |
| `EmbeddingError ... downloaded to ~/.cache/chroma` | Needs internet on first run (corporate proxies may block `chroma-onnx-models.s3.amazonaws.com`). Retry; or download once on another network. |
| `EmbeddingModelMismatchError` | The folder holds vectors from another model. Use a new `persist_directory`/`collection_name`, or delete `data\rag\chroma` and re-ingest. |
| `NoExtractableTextError` | The PDF is scanned. OCR it first (e.g. with an OCR tool) and ingest the result. |
| Everything returns `skipped_unchanged` | Expected for unchanged files. To force a rebuild, delete the data folder. |
| `PermissionError` deleting `data\rag\chroma` | Close Python processes that opened it (`rag.close()`), then retry. |
| `pypdf` prints `invalid pdf header` / `EOF marker not found` | Logged by pypdf for corrupted files; the failure is also returned in the result. |
| `Execution of scripts is disabled` | `Set-ExecutionPolicy -Scope Process Bypass`. |

## 11. Running tests

```powershell
$env:PYTHONPATH = "src"
py -m unittest discover -s tests -v                   # everything (RAG tests need no internet)
py -m unittest tests.test_rag_pipeline -v             # one file

$env:RAG_SMOKE = "1"                                  # real model + persistent ChromaDB
py -m unittest tests.test_rag_smoke_real_embeddings -v
```

Unit tests use a small deterministic hashing embedder (`tests/rag_test_support.py`, test-only) and
synthetic PDFs generated in code; real ChromaDB and real pypdf are used throughout. The smoke test
is skipped unless `RAG_SMOKE=1`, because it downloads the model.

## 12. Demo

```powershell
$env:PYTHONPATH = "src"
py examples\rag_demo.py                       # ingests examples\sample_docs\*.pdf (synthetic, invented company)
py examples\rag_demo.py --query "How long do refunds take?"
```
