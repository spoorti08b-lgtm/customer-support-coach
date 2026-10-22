# Architecture — AI Customer Support Coaching Assistant

**Project**: AI Customer Support Coaching Assistant  
**Internship**: Infosys Springboard Virtual Internship 7.0  
**Branch**: `feature/orchestrator` (integration branch)


# System Architecture

The AI Customer Support Coaching Assistant follows a modular architecture. Each component is responsible for a specific task, making the application easier to develop, test, and maintain.

### 1. Presentation Layer

The presentation layer provides the user interface through Streamlit.

**Main components:**

- `app.py` — Main entry point of the application.
- `views/setup.py` — Allows users to configure sessions, select interaction modes, and upload PDF documents.
- `views/console.py` — Provides the live coaching interface for customer interactions.
- `views/report.py` — Displays session reports, metrics, and conversation information.

### 2. Application Services Layer

This layer handles the main application operations, including session persistence, customer message analysis, and knowledge retrieval.

**Main components:**

- `utils/storage.py` — Saves and restores session information using JSON files.
- `utils/pipeline_stub.py` — Performs coaching analysis, customer simulation, and agent reply evaluation.
- `utils/rag_stub.py` — Processes uploaded PDFs and retrieves relevant knowledge chunks using the current retrieval implementation.
- `utils/validation.py` — Validates user inputs and helps prevent invalid data from entering the application.

### 3. Knowledge Retrieval Layer

The knowledge retrieval layer helps the coaching assistant find relevant information from uploaded documents.

**Workflow:**

- Users upload PDF documents through the Setup page.
- The system extracts text from the PDFs using `pypdf`.
- The extracted text is divided into smaller chunks.
- The chunks are stored in the generated knowledge index.
- When a customer message is analyzed, the retrieval component searches for relevant knowledge chunks.
- The retrieved information can support coaching suggestions and provide relevant source details.

The current implementation uses a lightweight retrieval stub. ChromaDB and ONNX-based embeddings are planned enhancements rather than current features.

### 4. Orchestration Layer

The orchestration layer coordinates the workflow between the session manager and the agent.

**Main components:**

- `orchestrator/orchestrator.py` — Coordinates the workflow through `run_workflow()`.
- `orchestrator/schemas.py` — Defines the workflow request and response models.
- `orchestrator/mock_components.py` — Provides mock session-manager and agent implementations.

**Orchestration workflow:**

1. Validates the incoming workflow request.
2. Retrieves the requested session through the session manager.
3. Invokes the agent with the session and customer message.
4. Validates the returned agent result.
5. Returns a workflow response indicating success or failure.
6. Handles unexpected errors safely.

The orchestrator is maintained as a separate component. It should be described as part of the live application flow only if it is explicitly connected to the Streamlit pipeline.

### 5. Session Management Layer

The session management layer handles session creation, retrieval, and updates.

**Responsibilities:**

- Creates and identifies coaching sessions.
- Retrieves session information using a session ID.
- Supports adding conversation messages and updating session status through the relevant interface.
- Uses JSON-based persistence in the current Streamlit implementation.
- May use SQLite in a future session-manager implementation.

The current JSON storage and the orchestrator's mock session manager are separate implementations and should not be treated as the same storage system.

### 6. Agent Layer

The agent layer generates coaching-related results for customer interactions.

**Responsibilities:**

- The mock agent receives a session and a customer message.
- It produces an `AgentResult` using the expected data structure.
- Keyword-based logic can be used to generate demonstration responses.
- The orchestrator validates the agent result before returning its workflow response.

The mock agent supports development and testing. More advanced AI agents can be integrated in future versions.

### 7. Shared Data Models Layer

The shared data models define the structures used to represent sessions, messages, and agent results.

**Main components:**

- `src/customer_support_coach/data_models.py` — Contains shared data models and enums.
- `orchestrator/schemas.py` — Contains orchestrator-specific request and response schemas.

These models help maintain consistent data formats and validate information exchanged between components.

### 8. Testing Layer

The testing layer checks the reliability of the application's components.

**Main components:**

- `tests/test_orchestrator.py` — Tests request validation, successful workflows, and failure handling.
- `smoke_test.py` — Provides basic application checks.
- `run_demo.py` — Demonstrates orchestrator behavior using sample scenarios.

Automated tests help identify errors before the components are integrated into the complete application.

### 9. Overall System Workflow

The application follows this workflow during a coaching session:

1. The user opens the Streamlit application.
2. The user selects an interaction mode and configures a coaching session.
3. The application creates the session and saves its information.
4. The user submits a customer message through the coaching console.
5. The coaching pipeline analyzes the message and retrieves relevant knowledge when required.
6. The application displays the available coaching insights and suggested response.
7. The user enters a proposed reply, which can be evaluated for tone and clarity.
8. The user ends the session and views the available report and conversation metrics.



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

**Member 1 — Shared Data Models**
- Responsible for Session, AgentResult, and enums.
- Branch: `feature/data-model-validation`

**Member 2 — Streamlit Frontend**
- Responsible for setup, console, report, and session persistence integration.
- Branch: `feature/streamlit-ui`

**Member 3 — Session Manager**
- Responsible for session management and SQLite database integration.
- Branch: `feature/session-manager`

**Member 4 — Orchestrator**
- Responsible for workflow coordination, schemas, and error handling.
- Branch: `feature/orchestrator`

**Member 5 — Mock Agent**
- Responsible for keyword-based coaching responses.
- Branch: `feature/mock-agent`

**Member 6 — Testing**
- Responsible for automated testing and end-to-end validation.
- Branch: `feature/testing`

**RAG Team — Knowledge Retrieval**
- Responsible for ChromaDB and the ONNX embedding pipeline.
- Branch: `feature/rag-pipeline`

## Technology Stack

- **Frontend:** Streamlit 1.35 or later
- **Data validation:** Pydantic v2
- **Session persistence:** JSON files stored in `data/sessions/`
- **PDF extraction:** pypdf 5.0 or later
- **Knowledge retrieval:** BM25-based retrieval implemented in `utils/rag_stub.py`
- **Vector database (planned):** ChromaDB 1.5 or later
- **Embedding model (planned):** ONNX-based `all-MiniLM-L6-v2`
- **Session database (planned):** SQLite at `data/customer_support.db`
- **Testing:** pytest 9.0 or later
- **Python:** Python 3.11 or later

## File Structure

The project is organized into the following directories and files.

**Main application**
- `app.py` — Main Streamlit application entry point.
- `requirements.txt` — Python dependencies.
- `run_demo.py` — Orchestrator command-line demonstration.
- `smoke_test.py` — Basic application checks.

**Streamlit configuration**
- `.streamlit/config.toml` — Application theme and configuration.

**Orchestrator — `orchestrator/`**
- `orchestrator.py` — Coordinates workflow execution.
- `schemas.py` — Defines workflow request and response models.
- `mock_components.py` — Provides mock session manager and agent components.
- `__init__.py` — Package initialization.

**Shared data models — `src/customer_support_coach/`**
- `data_models.py` — Defines shared data structures and enums.
- `__init__.py` — Package initialization.

**Application utilities — `utils/`**
- `storage.py` — Handles JSON-based session persistence.
- `rag_stub.py` — Handles PDF ingestion and BM25 knowledge retrieval.
- `validation.py` — Provides input validation.
- `pipeline_stub.py` — Implements coaching analysis, customer simulation, and reply evaluation.

**User interface — `views/`**
- `setup.py` — Session setup, mode selection, and PDF uploads.
- `console.py` — Live coaching console.
- `report.py` — Post-session report and metrics.
- `__init__.py` — Package initialization.

**Documentation — `docs/`**
- `architecture.md` — System architecture documentation.
- `orchestrator_integration.md` — Orchestrator integration details.

**Data — `data/`**
- `sample_pdfs/` — Sample knowledge-base documents.
- `sessions/` — Generated session data, excluded from Git.
- `kb_index.json` — Generated knowledge index, excluded from Git.

**Tests — `tests/`**
- `test_orchestrator.py` — Automated orchestrator tests.
- `__init__.py` — Package initialization.
