# Milestone 3 — Manual Mode, Replay Mode & Testing

**Project:** AI Customer Support Coaching Assistant
**Internship:** Infosys Springboard 7.0 — Batch 4 (Vidzai Digital)
**Milestone:** 3 (Week 5–6)
**Assigned scope:** Manual Mode, Replay Mode, integration with the existing
conversation/agent pipeline, and testing of both modes.
**Branch:** `feature/milestone3-manual-replay`
**Repository:** `customer-support-coach`

This folder organises the Milestone 3 testing artefacts only. The application
code lives in its established locations (`backend/`, `views/`, `utils/`,
`app.py`) and the executable tests stay in `tests/` so pytest discovers them.

---

## 1. Architecture findings (Phase 1 inspection)

The repository contains two generations of work that were merged over the
milestones. The **running application** is the root Streamlit app:

| Layer | Actual file(s) | What it does |
|---|---|---|
| Frontend entry point | `app.py` | Streamlit shell, sidebar navigation, saved-session list, URL `?sid=` restore, theme CSS |
| Setup page | `views/setup.py` | Interaction-mode selection (Simulator / Manual / Replay), product + scenario, PDF knowledge-base ingestion, transcript selection, session creation |
| Console page | `views/console.py` | Three-panel live coaching console (conversation / coaching feed / knowledge) for all three modes |
| Report page | `views/report.py` | Post-session metrics, sentiment journey, full transcript |
| Session persistence | `utils/storage.py` | JSON session store in `data/sessions/`, `DEFAULTS`, save/load/list/delete |
| Knowledge base | `utils/rag_stub.py` | PDF ingestion (pypdf), chunking, BM25 retrieval over `data/kb_index.json` |
| Rule-based pipeline | `utils/pipeline_stub.py` | `simulate_customer`, `analyze_turn`, `evaluate_agent_reply`, bundled sample transcript |
| Input validation | `utils/validation.py` | `MODES`, `validate_setup`, `validate_message`, legacy `parse_transcript` |
| Orchestrator (shared) | `orchestrator/` | `run_workflow`, `WorkflowRequest/Response`, mock session manager/agent |

The **agent layer** (Milestone 2 work) is a separate Python package:

| Component | Actual file(s) | Notes |
|---|---|---|
| Intent & Sentiment Analysis Agent | `backend/agents/intent_sentiment_agent.py` | `analyze_message()`, `IntentSentimentAgent().run(session, message)`, `IntentSentimentResult` |
| Conversation context / trajectory | `backend/agents/conversation_context.py` | `ConversationContext`, `SentimentTrajectoryPoint`, emotion/frustration/trend literals |
| Structured hand-offs | `backend/agents/agent_handoff.py` | `KnowledgeHandoff`, `EscalationHandoff`, `CoachingHandoff`, `AgentHandoff` |
| Knowledge Recommendation Agent | `backend/agents/knowledge_agent.py` | ChromaDB/sentence-transformers based; **not importable in this local environment** (see limitations) |
| Backend orchestrator | `backend/orchestrator/` | Contracts, knowledge schemas, `run_workflow` |
| Shared data models | `backend/core/data_models.py` | `Session`, `AgentResult`, `InteractionMode`, `Speaker` |
| Backend services | `backend/services/` | Alternative RAG/storage/validation implementations (ChromaDB) |

Exact duplicates exist (`backend/core` vs `src/customer_support_coach`,
`orchestrator/` vs `backend/orchestrator/`, `utils/` vs `backend/services/`)
because of the branch-based team workflow. Milestone 3 did **not** merge or
move these; it reused the ones the running app already imports.

### Existing functionality before Milestone 3

- Three-mode selector and session creation for Simulator / Manual / Replay.
- Manual Mode: paste a customer message, rule-based intent/sentiment/risk,
  suggested reply, PDF knowledge chunks, agent-reply tone score, saved session.
- Replay Mode: bundled or **`.txt`-only** transcript, "Next message" +
  "Restart replay", no previous/pause/resume, no preview.
- Three-panel console, escalation alert at ≥70% risk, post-session report.
- Streamlit AppTest was not used; tests covered data models, orchestrator,
  knowledge contracts and intent/emotion logic (141 tests in `backend/tests`).

### Gaps found (what Milestone 3 had to add)

Manual Mode
1. Pasted messages bypassed the real Intent & Sentiment Analysis Agent; only
   the rule-based `pipeline_stub` was used.
2. No duplicate-submission protection, no message ids, weak invalid-session
   handling.
3. No explicit handling for an analysis failure (it surfaced as a crash).

Replay Mode
4. Only `.txt` upload; no JSON/CSV support, size/type/structure validation.
5. No transcript preview before replay.
6. No Previous / Pause / Resume / Start controls; no total/position display.
7. No analysis caching: stepping back was impossible, and rebuilding the
   conversation could duplicate turns and analysis records.
8. Agent messages were not scored, and replay had no per-message context.

UI
9. Console had no dedicated replay controls and no fatigue-safe rerun
   behaviour (the message form was keyed on message count).

Pre-existing defect found during testing
10. `app.py` sidebar delete button was created without a label
    (`st.button(key=...)`), which raised `TypeError` and crashed the sidebar as
    soon as **any** saved session existed. Fixed with a visible "Delete" label.

---

## 2. What was implemented

New Streamlit-free logic package:

| File | Responsibility |
|---|---|
| `backend/modes/transcripts.py` | Upload validation (extension, 2 MB limit, empty/malformed) and JSON/CSV/TXT parsing, speaker normalisation, ordering, stable message ids, preview rows |
| `backend/modes/coaching.py` | Single analysis path for both modes: real `analyze_message()` (intent, sentiment, emotions, frustration, escalation risk, trend, context, hand-offs) + `rag_stub` retrieval + `pipeline_stub` tone scoring; rule-based fallback is flagged and never presented as agent output |
| `backend/modes/manual.py` | Session-safe turn submission: session-id/mode checks, empty/length validation, duplicate prevention, message ids, customer/agent separation, session isolation |
| `backend/modes/replay.py` | Position-based replay model (`transcript[:position]`), start/pause/resume/next/previous/restart/auto-advance, per-index analysis & tone caches so rewind never duplicates turns or records |

Modified files:

| File | Change |
|---|---|
| `views/console.py` | Manual Mode form and agent reply flow, full Replay controls, auto-play, richer coaching feed (emotions, intent confidence, trend, frustration level, escalation priority, coaching focus, fallback notice), escalation banner, flash messages |
| `views/setup.py` | Replay source: bundled sample or `.json`/`.csv`/`.txt` upload with validation, preview table, conversation id/format captions; resets replay caches on new session |
| `utils/storage.py` | Added persisted `replay_status`, `replay_analyses`, `replay_tones` defaults (legacy sessions load with defaults) |
| `app.py` | Fixed the unlabelled sidebar delete button that crashed the app |

Not changed: Simulator logic, report page, knowledge ingestion, agent
implementations, orchestrator, data models.

### Requirement tracing

| Requirement | Where |
|---|---|
| Manual Mode in mode selection | `views/setup.py` (existing radio, unchanged list) |
| Session creation, product/scenario context | `views/setup.py` |
| Message input, stored per session, history kept | `views/console.py` → `backend/modes/manual.py` |
| Existing multi-agent processing per message | `backend/modes/coaching.py` → `backend.agents.intent_sentiment_agent` |
| Knowledge recommendations | `coaching.retrieve_knowledge` → `utils/rag_stub` |
| Intent/sentiment/emotion/frustration/trend | `IntentSentimentResult` via `coaching.analyze_customer_turn` |
| Coaching + response suggestions | hand-off coaching fields + suggestion builder; agent replies scored by `pipeline_stub.evaluate_agent_reply` |
| Escalation alerts | `EscalationHandoff` + `coaching.escalation_alert` + console banner |
| UI update every turn | Streamlit rerun after each turn; three panels re-render |
| JSON/CSV/TXT upload, validation, preview | `backend/modes/transcripts.py`, `views/setup.py` |
| Parsing, speaker identification, ordering | `transcripts.parse_transcript_*` |
| Start / Pause / Resume / Next / Previous / Restart (+ optional auto-play) | `backend/modes/replay.py`, `views/console.py` |
| AI processing during replay, agent messages included but not classified | `replay._rebuild`, agent history normalisation in `coaching._agent_history` |
| Backward navigation without duplicate turns/records | position prefix rebuild + analysis cache |
| Three-panel console preserved | `views/console.py` layout unchanged (`st.columns([5,4,4])`) |

---

## 3. Testing artifacts in this folder

```
testing_m3/
├── README.md                          ← this report
├── manual_mode/
│   ├── test_cases.md                  ← TC-M-xx cases
│   └── test_results.md                ← execution results
├── replay_mode/
│   ├── test_cases.md                  ← TC-R-xx cases
│   └── test_results.md                ← execution results
├── integration/
│   ├── integration_test_cases.md      ← TC-I-xx cases + regressions
│   └── integration_results.md         ← execution results
├── sample_transcripts/
│   ├── sample_transcript.json         ← delayed order → refund escalation
│   ├── sample_transcript.csv          ← duplicate charge / payment
│   └── sample_transcript.txt          ← account access, confused → satisfied
├── test_reports/
│   └── milestone3_test_summary.md     ← totals, environment, limitations
└── screenshots/
    └── README.md                      ← no fabricated screenshots
```

Executable tests (kept in the framework's directory):

- `tests/test_manual_mode.py` (31 tests)
- `tests/test_replay_mode.py` (31 tests)
- `tests/test_m3_integration.py` (15 tests)
- `tests/test_m3_ui.py` (8 tests, Streamlit `AppTest`)

---

## 4. How to run

```bash
cd C:\Users\Admin\coding\customer-support-coach

# install (if needed)
pip install -r requirements.txt

# run the application
streamlit run app.py
# open http://localhost:8501
```

Milestone 3 tests:

```bash
python -m pytest tests/test_manual_mode.py tests/test_replay_mode.py \
    tests/test_m3_integration.py tests/test_m3_ui.py -v
```

Full root suite (see limitations):

```bash
python -m pytest -q
python -m pytest backend/tests -q
```

---

## 5. Known limitations (honest notes)

1. **Knowledge Recommendation Agent** (`backend/agents/knowledge_agent.py`,
   `backend/services/rag_stub.py`) depends on ChromaDB + sentence-transformers
   and cannot be imported in this local environment because of a
   TensorFlow/Protobuf version clash. The existing, app-integrated BM25
   `utils/rag_stub.py` is therefore the knowledge source for both modes.
   Five pre-existing root test modules (`test_m1.py`, `test_knowledge_contract.py`,
   `test_live_rag_integration.py`, `test_contextual_query.py`,
   `test_retrieval_metadata.py`) fail to *collect* for that same reason; this
   predates Milestone 3 and was confirmed before any change.
2. Replay auto-play uses a short `time.sleep` + rerun loop; manual stepping is
   the primary, fully tested control.
3. No screenshots are stored: none were captured for this milestone and none
   were generated artificially. The UI flows are verified by `AppTest` instead.
4. UI tests seed the console session state rather than clicking through the
   setup view and the console in one AppTest run; Streamlit's test harness
   cannot carry widget state across a view switch.
