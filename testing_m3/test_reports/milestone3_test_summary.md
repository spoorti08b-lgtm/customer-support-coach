# Milestone 3 — Test Summary

**Date:** 2026-11-22
**Branch:** `feature/milestone3-manual-replay`
**Scope:** Manual Mode, Replay Mode, integration with the existing
conversation/agent pipeline, testing.

---

## 1. Results at a glance

| Suite | File | Tests | Result |
|---|---|---|---|
| Manual Mode core | `tests/test_manual_mode.py` | 31 | 31 passed |
| Replay Mode core | `tests/test_replay_mode.py` | 31 | 31 passed |
| Integration / regression | `tests/test_m3_integration.py` | 15 | 15 passed |
| UI (Streamlit AppTest) | `tests/test_m3_ui.py` | 8 | 8 passed |
| **Milestone 3 total** | | **85** | **85 passed, 0 failed, 0 skipped** |
| Backend agent/data-model suite | `backend/tests` | 141 | 141 passed |
| Pre-existing root suite (runnable modules) | `tests/` excluding 5 un-importable modules | 117 | 117 passed |

Commands actually run:

```bash
python -m pytest tests/test_manual_mode.py tests/test_replay_mode.py \
    tests/test_m3_integration.py tests/test_m3_ui.py -q
# 85 passed in ~7s

python -m pytest backend/tests -q
# 141 passed

python -m pytest tests -q --ignore=tests/test_contextual_query.py \
  --ignore=tests/test_knowledge_contract.py --ignore=tests/test_live_rag_integration.py \
  --ignore=tests/test_m1.py --ignore=tests/test_retrieval_metadata.py
# 117 passed
```

---

## 2. Coverage against the brief

### Manual Mode
Created session, product/scenario context, message input, per-turn storage,
conversation history, existing-agent processing, knowledge retrieval, intent,
sentiment, emotions, frustration, sentiment trajectory/trend, coaching
suggestions, agent-reply tone scoring, escalation alerts, UI refresh per turn,
multi-turn context. Edge cases: empty, invalid session, duplicates, long
messages, API/analysis failures, missing context, concurrent sessions,
session isolation.

### Replay Mode
JSON / CSV / TXT upload with type, size, structure and speaker validation;
transcript preview; chronological ordering; stable message ids; start, pause,
resume, next, previous, restart and optional auto-play; position/total
display; per-message AI processing; agent messages recorded and scored but
never classified as customer messages; context and sentiment trajectory;
escalation alerts; correct behaviour when navigating backwards (no duplicate
turns or analyses).

### Integration
Both modes use one analysis path (`backend/modes/coaching.py` →
`backend.agents.intent_sentiment_agent` + `utils/rag_stub` +
`utils/pipeline_stub` tone scoring) and produce identical analysis key sets.
Sessions persist and restore; legacy sessions gain replay defaults; modes are
isolated. Simulator Mode, the legacy TXT parser, orchestrator workflow and the
intent agent were regression-tested.

---

## 3. Test environment

| Item | Value |
|---|---|
| OS | Windows (`win32`) |
| Python | 3.11.5 |
| Streamlit | 1.38.0 |
| pydantic | 2.9.2 |
| pytest | 8.3.3 |
| App URL used for manual checks | `http://localhost:8501` (`streamlit run app.py`) |

---

## 4. Failures and limitations (honest report)

1. **Pre-existing collection failures in the root suite.** Five test modules
   (`test_m1`, `test_knowledge_contract`, `test_live_rag_integration`,
   `test_contextual_query`, `test_retrieval_metadata`) cannot be imported in
   this environment because `backend/services/rag_stub.py` loads
   ChromaDB/sentence-transformers/TensorFlow with a mismatched Protobuf
   runtime. This was confirmed **before** any Milestone 3 change. These
   modules were excluded to run the rest of the suite; they were not fixed or
   altered.
2. **Knowledge Recommendation Agent unavailable.** For the same reason the
   ChromaDB knowledge agent could not be exercised. Both modes therefore use
   the app's existing BM25 `utils/rag_stub.py`, and knowledge tests stub the
   retrieval call to verify the integration contract. No claim of
   end-to-end testing against ChromaDB is made.
3. **No screenshots.** None were captured, and none were fabricated. The
   `screenshots/` folder contains only a note. UI behaviour is verified by
   Streamlit `AppTest`, which drives the real `app.py`.
4. **AppTest scope.** UI tests seed the console session state instead of
   clicking from setup into the console in a single run, because Streamlit's
   AppTest cannot retain widget state across a view switch. Setup and console
   flows are each driven through the real UI; the transition is covered by
   asserting the resulting session state.
5. **Auto-play timing** is exercised at the controller level
   (`auto_advance`) rather than by waiting on wall-clock sleeps in the UI.

---

## 5. Artefacts

- Test cases: `testing_m3/manual_mode/test_cases.md`,
  `testing_m3/replay_mode/test_cases.md`,
  `testing_m3/integration/integration_test_cases.md`
- Results: matching `*_results.md` files
- Sample transcripts: `testing_m3/sample_transcripts/`
- Architecture/implementation report: `testing_m3/README.md`
