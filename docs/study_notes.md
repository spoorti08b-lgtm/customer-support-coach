# Study Notes: AI Customer Support Coaching Assistant

**Author / Project:** Milestone 1 Architecture & Engineering Study  
**Scope:** Support Workflows, Coaching Methodologies, RAG Architecture, Multi-Agent Patterns  

---

## 1. Customer Support Workflows

Modern customer support operations balance three core metrics: First Contact Resolution (FCR), Average Handling Time (AHT), and Customer Satisfaction (CSAT) / Net Promoter Score (NPS). Support workflows generally follow a multi-tier lifecycle:

1. **Inbound Intake & Triage:** Requests arrive via omnichannel touchpoints (chat, email, portal, phone). Systems classify initial customer intent, perform identity verification, and tag sentiment/urgency.
2. **Tier-1 General Resolution:** Frontline agents handle high-volume, standardized scenarios (password resets, return policies, shipment tracking, billing clarifications). Agents rely on knowledge bases, standard operating procedures (SOPs), and pre-approved response macros.
3. **Escalation & Tier-2 Routing:** When an issue involves repeated contact, severe frustration, regulatory/legal threats, or technical anomalies, it must be escalated without forcing the customer to restart their explanation.
4. **Resolution, De-escalation & Follow-up:** The agent executes the solution, verifies satisfaction, offers clear timelines, and logs structured CRM interaction notes.

**Operational Challenges:** High agent turnover (30–45% annually), steep onboarding curves, inconsistent policy compliance, and the psychological strain of handling angry or confused customers.

---

## 2. Coaching Methodologies

Traditional support training relies on post-hoc quality assurance (QA): supervisors manually score 1–3% of past recordings weeks later using static rubrics. This delayed feedback loop fails to correct conversational missteps in real time.

Effective modern coaching applies adult learning theory and Kirkpatrick's Four-Level Training Evaluation:

- **In-the-Flow (Concurrent) Coaching:** Surfacing micro-feedback while the conversation is live (or during simulated practice) gives immediate reinforcement. Agents learn to detect emotional shifts, validate frustration before offering solutions, and maintain composure.
- **Rubric-Driven Evaluation:**
  - *Empathy & Emotional Validation:* Acknowledging inconvenience with sincerity rather than robotic repetition.
  - *Clarity & Concision:* Avoiding jargon, keeping turns between 15–60 words, and structuring steps logically.
  - *Action-Oriented Next Steps:* Providing clear ownership, specific deadlines, and explicit confirmation questions.
- **Deliberate Practice via Simulation:** Safe sandbox environments where agents role-play against diverse personas (Calm, Confused, Impatient, Frustrated, Angry) without risking real customer relationships or brand reputation.

---

## 3. Retrieval-Augmented Generation (RAG) Architecture

LLMs alone suffer from hallucinations, knowledge cutoff dates, and lack of private company policy context. RAG bridges this gap by grounding prompts in verifiable organizational documents.

Key RAG technical components:
- **Document Ingestion & Text Extraction:** Parsing clean layout text from policy/FAQ PDFs while stripping artifacts and handling multi-page structures.
- **Chunking Strategy:** Chunk size governs retrieval specificity. Coarse chunks (>1000 tokens) dilute semantic density and bloat prompt context; granular chunks (<100 tokens) lose surrounding context. A sliding window (e.g., 500 characters with 50-character overlap) preserves complete sentences while retaining page and document metadata.
- **Dense Vector Embeddings:** Deep transformer models (such as `all-MiniLM-L6-v2`) project text into dense semantic vector spaces (384 dimensions) where semantic similarity correlates with directional proximity (cosine similarity), outperforming sparse keyword search (TF-IDF/BM25) for synonyms and paraphrased questions.
- **Vector Store & Indexing:** An embedded persistent vector store (ChromaDB) stores embeddings with HNSW indexing for sub-millisecond approximate nearest neighbor (ANN) retrieval.
- **Deduplication:** Hash-based deterministic chunk identifiers prevent duplicate embeddings upon re-ingestion, maintaining consistent index integrity.

---

## 4. Multi-Agent Architectural Patterns

Complex conversational systems leverage specialized autonomous agents rather than a single monolithic prompt:

1. **Sequential / Pipeline Pattern:** Agents execute in a fixed linear sequence (e.g., Intake → Intent Extraction → Policy Retrieval → Response Formulation). Simple, but rigid when dynamic branching is needed.
2. **Supervisor / Orchestrator Pattern:** A central coordinator delegates sub-tasks to specialized domain agents (Sentiment Analyzer, Knowledge Recommender, Risk Monitor), validates inputs/outputs against strict schemas, and synthesizes the final turn.
3. **Peer-to-Peer Collaborative Pattern:** Agents pass messages directly to one another. Highly flexible, but difficult to test, trace, and debug deterministically.

---

## 5. Architectural Choices for This Project and Rationale

| Decision | Selected Technology / Pattern | Technical & Business Rationale |
|---|---|---|
| **Orchestration Pattern** | Orchestrator with Strict Schemas (`orchestrator/`) | Centralizes lifecycle management, prevents cascading failures, guarantees reproducible state transitions, and enforces contract validation via Pydantic models. |
| **Embedding Model** | `all-MiniLM-L6-v2` (`sentence-transformers`) | Fast, local CPU-friendly execution (384-dimensional embeddings), zero API latency, zero external cost, and no risk of leaking proprietary support policies to third-party endpoints. |
| **Vector Database** | `ChromaDB` (PersistentClient at `data/chroma`) | Lightweight, embedded (in-process SQLite + DuckDB/HNSW), zero server setup, native cosine distance support, and seamless cross-platform persistence. |
| **Chunking Configuration** | 500 characters, 50-character overlap | Fits concise support policy clauses, preserves page/doc metadata, and matches the optimal token window for MiniLM retrieval without truncating policy rules. |
| **Deduplication** | SHA-256 Content Hash + Chunk Index | Ensures idempotent PDF uploads; re-uploading identical documents updates or skips existing entries without index bloat or distorted retrieval statistics. |
| **UI Framework** | Streamlit (Wide Layout + Custom Glass Theme) | Rapid prototyping with instantaneous state updates, responsive multi-column dashboard, and zero frontend boilerplate. |
