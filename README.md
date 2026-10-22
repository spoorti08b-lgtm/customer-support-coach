# AI Customer Support Coaching Assistant

A team project built during the Infosys Springboard Virtual Internship 7.0.

The application helps customer support employees practice and improve their
responses through live coaching, real-time escalation-risk assessment, and
a knowledge base built from uploaded support documents.

---

## Project status

| Module | Member | Branch | Status |
|---|---|---|---|
| Shared data models | Member 1 | `feature/data-model-validation` | ✅ Complete |
| Streamlit frontend | Member 2 | `feature/streamlit-ui` | ✅ Complete |
| Session manager | Member 3 | `feature/session-manager` | ✅ Complete |
| Orchestrator | Member 4 | `feature/orchestrator` | ✅ Complete |
| Mock agent | Member 5 | `feature/mock-agent` | ✅ Complete |
| Testing | Member 6 | `feature/testing` | In progress |
| RAG pipeline | — | `feature/rag-pipeline` | ✅ Complete |

---

## Features

- **Three interaction modes:** Simulator (AI customer), Manual (paste messages), Replay (replay a transcript).
- **Knowledge base:** Upload support PDFs → chunked, indexed, top-3 relevant chunks retrieved per customer message with source filenames.
- **Live coaching console:** Sentiment, intent, escalation risk, suggested replies, tone scoring.
- **Session persistence:** Sessions saved to `data/sessions/` and restored after a browser refresh via the `?sid=` URL parameter.
- **Orchestrator:** Central workflow coordinator with Pydantic validation and clean error handling.
- **Post-session report:** Sentiment journey chart, peak escalation risk, coaching recommendations.

---

## Technology stack

| Component | Technology |
|---|---|
| Frontend | Streamlit ≥ 1.35 |
| Data validation | Pydantic v2 |
| PDF extraction | pypdf ≥ 5.0 |
| Knowledge retrieval | BM25 TF-IDF (standalone) |
| Session persistence | JSON files (`data/sessions/`) |
| Vector DB (future) | ChromaDB + ONNX all-MiniLM-L6-v2 |
| Session database (future) | SQLite (`data/customer_support.db`) |
| Testing | pytest ≥ 9.0 |
| Python | 3.11+ |

---

## Repository structure

```
customer-support-coach/
├── app.py                          ← Streamlit entry point
├── requirements.txt
├── run_demo.py                     ← Orchestrator CLI demo
├── .streamlit/
│   └── config.toml                 ← Theme + upload size config
├── orchestrator/                   ← Member 4
│   ├── orchestrator.py             ← run_workflow()
│   ├── schemas.py                  ← WorkflowRequest / WorkflowResponse
│   ├── mock_components.py
│   └── __init__.py
├── src/
│   └── customer_support_coach/     ← Member 1
│       ├── data_models.py
│       └── __init__.py
├── utils/                          ← Member 2
│   ├── storage.py                  ← Session persistence
│   ├── rag_stub.py                 ← PDF ingestion + retrieval
│   ├── validation.py               ← Form validation
│   └── pipeline_stub.py            ← Coaching analysis
├── views/                          ← Member 2
│   ├── setup.py                    ← Setup page
│   ├── console.py                  ← Live coaching console
│   └── report.py                   ← Post-session report
├── docs/
│   ├── architecture.md             ← Architecture diagram
│   └── orchestrator_integration.md ← Orchestrator contract
├── data/
│   └── sample_pdfs/                ← Sample PDFs for demo
└── tests/
    └── test_orchestrator.py        ← 11 orchestrator tests
```

---

## Setup

```bash
# Clone and enter the repository
git clone https://github.com/spoorti08b-lgtm/customer-support-coach.git
cd customer-support-coach
git checkout feature/orchestrator

# (Recommended) create a virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Linux / macOS

# Install dependencies
pip install -r requirements.txt
```

---

## Running the application

**Terminal 1 — Start the Streamlit app:**

```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## Quick workflow

1. Open the setup page → upload one or more PDFs → click **Ingest PDFs**.
2. Select an interaction mode (Simulator / Manual / Replay).
3. Fill in product context and customer scenario → click **Start coaching session**.
4. In the console: add or receive customer messages and watch the coaching panel.
5. Click **End session** → view the post-session report.
6. Refresh the browser — the session restores automatically from the URL.

---

## Running the orchestrator demo

```bash
py -3 run_demo.py
```

Runs four scenarios: successful workflow, schema validation rejection,
missing session, and agent failure.

---

## Running the tests

```bash
py -3 -m pytest tests/test_orchestrator.py -v
```

All 11 tests pass. No external services are required.

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full system diagram.

---

## Integration

See [`docs/orchestrator_integration.md`](docs/orchestrator_integration.md)
for the interfaces that the session manager and agent must implement.

---

## Current limitations

- The knowledge base uses BM25 (keyword matching). ChromaDB + semantic embeddings
  are implemented in `feature/rag-pipeline` and will be merged in a later milestone.
- The coaching analysis (`pipeline_stub.py`) uses rule-based heuristics.
  A real LLM agent will replace it in a later milestone.
- The SQLite session manager (`feature/session-manager`) is not yet merged;
  sessions are currently stored as JSON files in `data/sessions/`.
