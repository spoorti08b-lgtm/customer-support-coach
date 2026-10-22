# Orchestrator Integration Notes

**Module:** Orchestrator  
**Developed by:** Member 4  
**Project:** AI Customer Support Coaching Assistant — Infosys Springboard Virtual Internship 7.0

---

## 1. Main function signature

```python
from orchestrator import run_workflow, WorkflowRequest, WorkflowResponse

response = run_workflow(
    request=WorkflowRequest(session_id="sess-abc", message="Where is my order?"),
    session_manager=your_session_manager,
    agent=your_agent,
)
```

The function **never raises an exception**. It always returns a `WorkflowResponse`.

---

## 2. WorkflowRequest

```python
@dataclass
class WorkflowRequest:
    session_id: str   # Must be 1–128 chars: letters, digits, _ . : -
    message: str      # Must not be empty or whitespace-only
```

---

## 3. WorkflowResponse

```python
@dataclass
class WorkflowResponse:
    session_id: str | None   # The session ID from the request (None only when invalid)
    status: str              # "completed" | "failed"
    result: dict | None      # Agent output dict on success; None on failure
    error: str | None        # Plain-English error message on failure; None on success
```

### Response rules
- `status == "completed"` → `result` is a non-empty dict, `error` is `None`
- `status == "failed"` → `error` is a string, `result` is `None`
- The error message is always safe to display (no tracebacks, no sensitive data)

---

## 4. Session Manager interface (Member 3)

The orchestrator calls exactly **one method**:

```python
def get_session(session_id: str) -> Session | None:
    """
    Return the Session object for the given ID.
    Return None if the session does not exist.
    Raise an exception only for unexpected infrastructure errors
    (the orchestrator will catch it safely).
    """
```

The returned object must be an instance of `customer_support_coach.data_models.Session`.

### Optional — workflow status updates
If Member 3's session manager supports persisting workflow status, the orchestrator
can call an additional method. Proposed signature (confirm with Member 3 before using):

```python
def update_session_status(session_id: str, status: str) -> None:
    """Store "active", "completed", or "cancelled" for the session."""
```

This is **not implemented yet**. Do not add it until Member 3 confirms the interface.

---

## 5. Agent interface (Member 5)

The orchestrator calls exactly **one method**:

```python
def run(session: Session, message: str) -> AgentResult:
    """
    Analyse the customer message in the context of the session.
    Return an AgentResult (from customer_support_coach.data_models).
    Raise an exception only on a genuine failure.
    """
```

The returned object must be an instance of `customer_support_coach.data_models.AgentResult`.
Its `.result` field must be a non-empty dict.

---

## 6. Shared data models (Member 1)

All three modules use the models from `src/customer_support_coach/data_models.py`:

| Class | Used by |
|---|---|
| `Session` | Session manager → orchestrator → agent |
| `AgentResult` | Agent → orchestrator → response |
| `ConversationMessage` | Agent (optional, for conversation history) |
| `ValidationError` | All modules |

The copy in this branch (`src/customer_support_coach/`) is **temporary**.
Replace it with Member 1's final file when branches are merged.

---

## 7. Failure representation

All failures follow the same shape:

```python
WorkflowResponse(
    session_id="sess-abc",   # or None if the session_id itself was invalid
    status="failed",
    result=None,
    error="Plain-English description of what went wrong.",
)
```

Failures handled:

| Scenario | Error message (example) |
|---|---|
| Empty or invalid `session_id` | `"Invalid request: session_id is missing or contains invalid characters."` |
| Whitespace-only `message` | `"Invalid request: message must not be empty or contain only whitespace."` |
| Session not found | `"Session 'sess-xyz' was not found."` |
| Session manager crash | `"Could not retrieve the session. Please try again."` |
| Agent crash | `"The agent encountered an error. Please try again."` |
| Agent returns wrong type | `"The agent returned an unexpected response format."` |
| Agent returns empty result | `"The agent returned an empty result."` |

---

## 8. Temporary components (Member 4 only)

These files are **temporary** and exist only in the orchestrator branch:

| File | Replaces |
|---|---|
| `orchestrator/mock_components.py → MockSessionManager` | Member 3's `SessionManager` |
| `orchestrator/mock_components.py → MockAgent` | Member 5's real agent |
| `src/customer_support_coach/` (copied files) | Member 1's merged package |

The orchestrator (`orchestrator/orchestrator.py`) **does not import** `mock_components.py`.
Swap the injected dependencies in `run_demo.py` and `tests/test_orchestrator.py` to use real implementations.

---

## 9. For Member 2 (Frontend / Streamlit)

Call `run_workflow()` from your Streamlit page:

```python
from orchestrator import run_workflow, WorkflowRequest

response = run_workflow(
    request=WorkflowRequest(session_id=st.session_state.session_id, message=user_input),
    session_manager=real_session_manager,
    agent=real_agent,
)

if response.status == "completed":
    st.success(response.result.get("response", ""))
    st.info(response.result.get("coaching_tip", ""))
else:
    st.error(response.error)
```

---

## 10. For Member 6 (Testing)

- All orchestrator tests live in `tests/test_orchestrator.py`.
- Run with: `py -3 -m pytest tests/test_orchestrator.py -v`
- The tests use `MockSessionManager` and `MockAgent` — no external services needed.
- See the test file for the exact input/output expectations for each scenario.

---

## 11. Session mode handling

The `Session` dataclass has a `mode` field (`InteractionMode` enum):

| Mode | Value | Session requirement |
|---|---|---|
| Simulator | `"simulator"` | `session.scenario` must not be `None` (enforced by `Session.__post_init__`) |
| Manual | `"manual"` | `session.scenario` is optional |
| Replay | `"replay"` | Uses existing session history |

The orchestrator passes the **full `Session` object** to the agent via `agent.run(session, message)`.
Mode-specific behaviour (e.g. replaying history, using the scenario text) is the agent's responsibility.
The orchestrator does not branch on mode — it treats all three modes the same way at the workflow level.

To check the mode in the agent or frontend:

```python
from customer_support_coach.data_models import InteractionMode

if session.mode == InteractionMode.SIMULATOR:
    # use session.scenario
elif session.mode == InteractionMode.MANUAL:
    # use the customer message directly
elif session.mode == InteractionMode.REPLAY:
    # load historical messages from session.metadata or session manager
```

---

## 12. Retrieval integration (not yet implemented)

The retrieval pipeline (PDF ingestion, chunking, embeddings, ChromaDB) is **not yet available** in
any branch as of Milestone 1.

When it becomes available, the recommended integration point is:

```python
# In run_workflow(), after retrieving the session and before calling the agent:
retrieved_chunks = retrieval_service.search(query=message, top_k=3)
# Pass chunks to the agent via an extended request or session.metadata.
```

The orchestrator is **already compatible** with this approach — no structural changes are needed.
The retrieval service will be a third injected dependency alongside `session_manager` and `agent`.

**Do not add fake or hardcoded retrieved chunks.** When retrieval is unavailable, omit it entirely.
