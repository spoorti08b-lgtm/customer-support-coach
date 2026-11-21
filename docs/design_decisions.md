# System Design & Architecture Decisions

**Project:** AI Customer Support Coaching Assistant  
**Milestone:** 1 (Foundation & Retrieval Pipeline)  
**Author:** AI Engineering & Support Platform Team  

---

## 1. Local-First Dense Vector Retrieval (RAG)

### Context & Decision
Customer support coaching requires sub-second retrieval over internal policy and FAQ documents without transmitting sensitive company data or customer records to third-party cloud APIs. We chose **ChromaDB (`PersistentClient`)** paired with the **SentenceTransformers `all-MiniLM-L6-v2`** model.

### Key Justifications
- **Embedding Dimensions & Latency:** `all-MiniLM-L6-v2` maps text chunks into a compact 384-dimensional dense vector space. Inference executes locally on CPU in ~15 ms per query, avoiding external rate limits and API costs.
- **Cosine Similarity Metric:** Cosine distance is used ($1 - \text{distance}$) as it normalizes for text chunk length variations across differing policy guidelines.
- **Persistent Storage:** Stored at `data/chroma/`, ChromaDB's SQLite + HNSW index survives server reboots without re-indexing.
- **Deduplication:** Chunks receive a deterministic ID formed by the SHA-256 hash of the source file, page number, and chunk index (`<hash>_p<page>_c<idx>`). Re-uploading the same PDF triggers an upsert, preventing duplicate chunk inflation.

---

## 2. Text Preprocessing & Chunking Strategy

### Context & Decision
Support policies contain discrete instructions (e.g. return windows, refund turnaround days, warranty criteria). We selected a **sliding window of 500 characters with a 50-character overlap**.

### Key Justifications
- **Context Granularity:** 500 characters comfortably envelopes individual policy rules (typically 2–3 sentences) while preventing topic dilution.
- **Overlap Protection:** 50 characters of overlap ensures that boundary conditions (such as lists or conditions split across windows) retain continuity across adjacent chunks.
- **Metadata Retention:** Each chunk carries `doc_name`, `page`, and chunk sequence numbers, allowing citations in user-facing UI badges.

---

## 3. Flat Session Schema & Storage Architecture

### Context & Decision
Milestone 1 transitions from nested legacy schemas (`product_context: {"product": ...}`, duplicate `persona` in `metadata`) to a **single, flat source of truth** stored in `data/sessions/<session_id>.json`.

### Schema Specification
```json
{
  "session_id": "sess-47d9abb1",
  "mode": "Simulator",
  "product": "Acme Online Store",
  "scenario": "Customer was charged twice for their monthly subscription.",
  "persona": "Frustrated",
  "max_turns": 4,
  "replay_transcript": null,
  "kb_documents": ["returns_and_refunds.pdf"],
  "status": "configured",
  "created_at": "2026-10-23T12:48:28+05:30"
}
```

### Key Justifications
- **Zero Ambiguity:** Fields like `persona` and `max_turns` are cleanly isolated to `Simulator` mode (set to `null` in `Manual` and `Replay`).
- **Tolerant Migration:** A normalization layer in `utils/storage.py` allows existing sessions created under earlier schemas to load without schema breakage.
- **Offline Inspection:** Plain JSON files in `data/sessions/` can be audited, backed up, or downloaded directly from the Streamlit UI.

---

## 4. Multi-Agent Orchestration Topology

### Context & Decision
The central orchestrator coordinates six specialized agents across milestones using a hub-and-spoke pipeline:
1. **Customer Simulator [M2]:** Generates persona-driven turns.
2. **Intent & Sentiment Monitor [M2]:** Real-time emotion and frustration tracking.
3. **Knowledge Recommender [M3]:** Direct vector retrieval against ChromaDB.
4. **Coaching & Response Recommender [M3]:** Real-time empathy and clarity suggestions.
5. **Escalation Risk Monitor [M3]:** Churn and SLA threshold tracking.
6. **Post-Interaction Summary [M4]:** Resolution score and Kirkpatrick evaluation.

In Milestone 1, the orchestrator exposes a validated contract (`run_workflow`) that returns `{"status": "ready", "session_id": ..., "mode": ...}` while passing all Pydantic boundary checks.
