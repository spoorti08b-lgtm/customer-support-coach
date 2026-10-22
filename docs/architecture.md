# Architecture — AI Customer Support Coaching Assistant

Project: AI Customer Support Coaching Assistant  
Internship: Infosys Springboard Virtual Internship 7.0  
Branch: `feature/orchestrator` (integration branch)


# System Architecture


┌─────────────────────────────────────────────────────────────┐
│                    USER (Browser)                           │
│                  http://localhost:8501                      │
└────────────────────────┬────────────────────────────────────┘
                         │  HTTP (Streamlit)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               STREAMLIT FRONTEND  (app.py)                  │
│                                                             │
│  views/setup.py     ← Session setup, PDF upload, mode pick  │
│  views/console.py   ← Live coaching console (3 panels)      │
│  views/report.py    ← Post-session metrics & transcript     │
└───────┬─────────────────────────┬───────────────────────────┘
        │                         │
        ▼                         ▼
┌───────────────────┐   ┌─────────────────────────────────────┐
│  utils/storage.py │   │      utils/pipeline_stub.py         │
│                   │   │                                     │
│  JSON file store  │   │  analyze_turn()   → coaching data   │
│  data/sessions/   │   │  simulate_customer() → Simulator    │
│  ?sid= URL param  │   │  evaluate_agent_reply() → tone      │
│                   │   └────────────────┬────────────────────┘
│  Session restore  │                    │
│  after refresh ✓  |                    ▼
└───────────────────┘   ┌─────────────────────────────────────┐
                        │       utils/rag_stub.py             │
                        │  (BM25 retrieval, no ChromaDB)      │
                        │                                     │
                        │  ingest_pdfs() → chunk + index PDF  │
                        │  retrieve(query, k=3) → top-3 chunks│
                        │  data/kb_index.json  (persistent)   │
                        └─────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               ORCHESTRATOR  (orchestrator/)                 │
│                         Member 4                            │
│                                                             │
│  orchestrator.py → run_workflow(request, sm, agent)         │
│  schemas.py      → WorkflowRequest / WorkflowResponse       │
│  mock_components → MockSessionManager / MockAgent           │
│                                                             │
│  Workflow:                                                  │
│  1. Validate WorkflowRequest (Pydantic)                     │
│  2. session_manager.get_session(session_id)                 │
│  3. agent.run(session, message) → AgentResult               │
│  4. Validate AgentResult type + content                     │
│  5. Return WorkflowResponse (completed | failed)            │
└────────────┬──────────────────────────┬─────────────────────┘
             │                          │
             ▼                          ▼
┌────────────────────────┐  ┌───────────────────────────────┐
│   SESSION MANAGER      │  │        MOCK AGENT             │
│   Member 3             │  │        Member 5               │
│                        │  │                               │
│  get_session(id)       │  │  MockAgent.run(session, msg)  │
│  create_session(...)   │  │  → AgentResult (pydantic)     │
│  add_message(...)      │  │                               │
│  update_session_status │  │  Member 5's MockAgent uses    │
│                        │  │  generate_response(msg) —     │
│  SQLite backend:       │  │  keyword-based responses.     │
│  data/customer_        │  │  Orchestrator's own           │
│  support.db            │  │  mock_components.py wraps     │
│  (sessions, messages,  │  │  it to AgentResult format.    │
│   agent_results)       │  │                               │
└────────────────────────┘  └───────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│           SHARED DATA MODELS  (src/)   Member 1             │
│                                                             │
│  Session           ConversationMessage    AgentResult       │
│  InteractionMode   SessionStatus          Speaker           │
│  ValidationError   (all dataclasses + enums)                │
└─────────────────────────────────────────────────────────────┘


## Data Flow — Manual Mode (End-to-End)

1. The user opens `http://localhost:8501`.

2. Setup Page: The user selects Manual mode and enters the product details and scenario.

3. The user clicks Start Coaching Session.
   - `storage.save()` saves the session data to `data/sessions/{sid}.json`.
   - The URL is updated to `?sid={sid}`.

4. The Console page loads using the session ID.

5. **Customer Message Analysis:** The user pastes a customer message.
   - `pipeline_stub.analyze_turn(message, history, config)` processes the message.
   - `rag_stub.retrieve(message, k=3)` retrieves the three most relevant knowledge chunks.
   - The system loads `data/kb_index.json`, calculates BM25 scores, and returns the top three chunks.
   - The results display sentiment, intent, escalation risk, a suggested reply, and three knowledge chunks with their source filenames.

6. Agent Reply Evaluation: The user enters a reply, and `evaluate_agent_reply()` evaluates its tone and clarity.

7. Session Completion: The user clicks End Session, and `report.render()` displays the session metrics.

8. Session Restoration: When the user refreshes the browser, `bootstrap()` reads the session ID from `?sid=` and restores the existing session.

## Data Flow — PDF Ingestion

1. The user uploads one or more PDF files on the Setup page.

2. The user clicks **Ingest PDFs**.
   - `rag_stub.ingest_pdfs(files)` processes the uploaded files.
   - `pypdf` extracts text page by page.
   - `_chunk()` splits the extracted text into 120-word windows with a 20-word overlap.
   - The resulting chunks are stored in `data/kb_index.json`.
   - The interface displays the number of chunks stored, the number of files processed, and the total number of chunks in the knowledge base.

3. Knowledge Retrieval: When `retrieve(query, k=3)` is called, BM25-based relevance scoring ranks the available chunks and returns the top three results in the following format:
   - `source`: The original filename.
   - `page`: The source page number.
   - `text`: The extracted text.
   - `score`: The relevance score.



## Team Roles and Branches
_________________________________________________________________________________________________________________
|   Member |                 Role                                             |          Branch                  |
|__________|__________________________________________________________________|__________________________________|                                                                     |                                  |
| Member 1 | Shared data models (Session, AgentResult, enums)                 | feature/data-model-validation    |
| Member 2 | Streamlit frontend (setup, console, report, session persistence) | feature/streamlit-ui             |
| Member 3 | Session manager and SQLite database                              | feature/session-manager          |
| Member 4 | Orchestrator (workflow coordination, schemas, error handling)    | feature/orchestrator             |
| Member 5 | Mock agent (keyword-based coaching responses)                    | feature/mock-agent               |
| Member 6 | Testing and end-to-end validation                                | feature/testing                  |
| RAG Team | ChromaDB and ONNX embedding pipeline                             | `feature/rag-pipeline            |
|__________|__________________________________________________________________|__________________________________|

## Technology Stack
 __________________________________________________________________________
|        Component           |                  Technology                 |
| ___________________________|_____________________________________________|                                        
| Frontend                   | Streamlit ≥ 1.35                            |
| Data validation            | Pydantic v2                                 |
| Session persistence        | JSON files (`data/sessions/`)               |
| PDF extraction             | pypdf ≥ 5.0                                 |
| Knowledge retrieval        | BM25-based retrieval (`utils/rag_stub.py`)  |
| Vector database (future)   | ChromaDB ≥ 1.5 with ONNX `all-MiniLM-L6-v2` |
| Session database (future)  | SQLite (`data/customer_support.db`)         |
| Testing                    | pytest ≥ 9.0                                |
| Python                     | 3.11+                                       |
|____________________________|_____________________________________________|


## File Structure

customer-support-coach/
├── app.py                          ← Streamlit entry point
├── requirements.txt
├── run_demo.py                     ← Orchestrator CLI demo (4 scenarios)
├── .streamlit/
│   └── config.toml                 ← Theme + upload size config
├── orchestrator/                   ← Member 4
│   ├── orchestrator.py             ← run_workflow()
│   ├── schemas.py                  ← WorkflowRequest / WorkflowResponse
│   ├── mock_components.py          ← MockSessionManager, MockAgent
│   └── __init__.py
├── src/
│   └── customer_support_coach/     ← Member 1
│       ├── data_models.py          ← Session, AgentResult, enums
│       └── __init__.py
├── utils/                          ← Member 2 utilities
│   ├── storage.py                  ← JSON session persistence
│   ├── rag_stub.py                 ← PDF ingestion + BM25 retrieval
│   ├── validation.py               ← Form validation
│   └── pipeline_stub.py            ← Rule-based coaching analysis
├── views/                          ← Member 2 views
│   ├── setup.py                    ← Setup page (3 modes)
│   ├── console.py                  ← Live coaching console
│   └── report.py                   ← Post-session report
├── docs/
│   ├── orchestrator_integration.md ← Member 4 integration contract
│   └── architecture.md             ← This document
├── data/                           ← Runtime data (git-ignored)
│   ├── sessions/                   ← Saved session JSON files
│   └── kb_index.json               ← BM25 knowledge base index
└── tests/
    └── test_orchestrator.py        ← 11 orchestrator tests

