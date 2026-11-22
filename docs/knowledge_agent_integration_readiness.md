# Knowledge Recommendation Agent — Integration Readiness Guide

**Module:** Knowledge Recommendation Agent
**Component:** `backend.services.knowledge_agent.KnowledgeRecommendationAgent`
**Contract Schemas:** `backend.orchestrator.knowledge_schemas`
**Author:** Knowledge Recommendation Team
**Status:** **READY FOR INTEGRATION**
**Verified Regression:** 89 passed, 0 failed

---

## 1. Overview

The Knowledge Recommendation Agent retrieves policy and support documentation chunks from local persistent ChromaDB storage (`data/chroma/`) using dense semantic embeddings (`all-MiniLM-L6-v2`) and contextual query construction.

It supports two distinct invocation patterns:
1. **Direct Service / Request API (`agent.recommend`):** Consumes a typed Pydantic v2 `KnowledgeRecommendationRequest` and returns a `KnowledgeRecommendationResponse`.
2. **Orchestrator Standard Agent Interface (`agent.run`):** Consumes `(session: Session, message: str)` and returns an `AgentResult` complying with `docs/orchestrator_integration.md`.

---

## 2. Pydantic v2 Contract Specifications

### 2.1. Request Schema: `KnowledgeRecommendationRequest`

```python
from backend.orchestrator.knowledge_schemas import (
    KnowledgeRecommendationRequest,
    ConversationHistoryItem,
)

request = KnowledgeRecommendationRequest(
    message="What is the standard delivery timeframe?",  # Required (non-empty str)
    intent="Delivery / order",                           # Optional str
    product="Acme Gadget Pro",                           # Optional str
    history=[                                            # Optional list of turns
        ConversationHistoryItem(
            speaker="customer",                          # "customer" | "agent" | "user" | "assistant"
            content="I ordered standard shipping.",
            turn_number=1,
        )
    ],
    limit=3,                                             # Optional int in [1, 20], default 3
    session_id="sess-abc",                               # Optional str
    kb_identifier="support_kb",                          # Optional str
)
```

### 2.2. Response Schema: `KnowledgeRecommendationResponse`

```python
class KnowledgeRecommendationResponse(BaseModel):
    agent_name: str = "knowledge_recommendation"
    status: KnowledgeExecutionStatus       # SUCCESS | NO_MATCH | ERROR
    query: str                             # The actual query sent to ChromaDB
    passages: list[RetrievedPassage]       # List of retrieved passages (empty on NO_MATCH)
    no_match: bool                         # True if status == NO_MATCH
    error: str | None                      # Error message string if status == ERROR
    session_id: str | None                 # Associated session ID
```

### 2.3. Passage Schema: `RetrievedPassage`

```python
class RetrievedPassage(BaseModel):
    text: str                              # Text snippet content
    source: str                            # Filename (e.g. "shipping_and_delivery.pdf")
    doc_name: str                          # Document display name
    chunk_id: str | None                   # Stored ChromaDB ID (e.g. "e11e1dd62150604a_p1_c0")
    page: int                              # Source PDF page number (1-based)
    rank: int                              # Rank in result list (1-based)
    score: float | None                    # Cosine similarity score in [0.0, 1.0]
```

---

## 3. Invocation Methods

### Option A: For the Orchestrator (`agent.run`)

The orchestrator invokes the agent with `(session, message)`:

```python
from backend.core.data_models import Session, AgentResult
from backend.services.knowledge_agent import KnowledgeRecommendationAgent

agent = KnowledgeRecommendationAgent()
result: AgentResult = agent.run(session=current_session, message="Where is my order?")

# AgentResult fields:
# result.agent_name -> "knowledge_recommendation"
# result.status     -> "success" | "no_match" | "error"
# result.result     -> dict containing serialized KnowledgeRecommendationResponse
```

### Option B: Direct Typed Call (`agent.recommend`)

```python
response = agent.recommend(request)

if response.status == KnowledgeExecutionStatus.SUCCESS:
    for passage in response.passages:
        print(f"Rank {passage.rank}: [{passage.source} p.{passage.page}] (score: {passage.score})")
        print(f"  {passage.text}\n")
elif response.status == KnowledgeExecutionStatus.NO_MATCH:
    print("No relevant support documentation found above confidence threshold.")
elif response.status == KnowledgeExecutionStatus.ERROR:
    print(f"Retrieval error: {response.error}")
```

---

## 4. Response Status and Score Semantics

| Status | `no_match` | Passages | Score Range | Description |
|---|---|---|---|---|
| `SUCCESS` | `False` | 1 to $K$ | $\ge 0.20$ | Relevant passages found in the knowledge base. |
| `NO_MATCH` | `True` | Empty `[]` | N/A | Query was out-of-domain or all hits fell below $0.20$. |
| `ERROR` | `False` | Empty `[]` | N/A | Database or retrieval exception occurred safely. |

### Score Semantics
- Scores are **cosine similarities**: $\text{score} = 1.0 - \text{distance}$.
- **$\ge 0.50$:** High confidence direct or paraphrased answer.
- **$0.30 - 0.50$:** Moderate confidence; passage is topically related.
- **$0.20 - 0.30$:** Weak relevance; customer inquiry may be asking about a policy variation not covered in text.
- **$< 0.20$:** Automatically filtered out by the agent and returned as `NO_MATCH`.

---

## 5. Local Setup & Persistence Requirements

1. **Vector Store:** ChromaDB persistent storage is located at `data/chroma/`. It is auto-loaded by `rag_stub.get_chroma_client()`.
2. **Sample Documents:** 3 PDFs in `data/sample_pdfs/`:
   - `returns_and_refunds.pdf`
   - `account_and_password_faq.pdf`
   - `shipping_and_delivery.pdf`
3. **Automatic Ingestion:** If `data/chroma/` is empty or cleared, `rag_stub.load_sample_pdfs()` automatically indexes the sample PDFs on first retrieval.
4. **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2` is downloaded to local HuggingFace cache once and reused. Cached in memory via `@st.cache_resource`.

---

## 6. Guidance for Other Team Members

### For Orchestrator Team
- Use `agent.run(session, message)`.
- The returned `AgentResult.result` contains the full serialized response dictionary.
- If `result.status == "no_match"`, the orchestrator can proceed with generic conversational coaching without knowledge passages.
- If `result.status == "error"`, log the error string in `result.result["error"]` without crashing the workflow.

### For Streamlit Frontend Team
- In the coaching sidebar or knowledge recommendation card:
  - Display top passage text, source filename, and page number: e.g. `[Returns Policy, Page 1]`.
  - For scores $< 0.40$, optionally render a subtle badge: `Low confidence (topical match)`.
  - If `no_match == True`, display: *"No matching knowledge base documentation found."*

### For QA & Testing Team
- Run unit tests: `python -m pytest tests/test_evaluation_metrics.py tests/test_knowledge_contract.py tests/test_contextual_query.py tests/test_retrieval_metadata.py`
- Run live integration tests: `python -m pytest tests/test_live_rag_integration.py`
- Run full evaluation benchmark: `python -m backend.evaluation.eval_runner`
