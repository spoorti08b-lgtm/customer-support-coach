# Integration & Regression — Test Results

**Executed:** 2026-11-22
**Environment:** Windows, Python 3.11.5, Streamlit 1.38.0, pydantic 2.9.2,
pytest 8.3.3
**Commands and outcomes:**

```bash
python -m pytest tests/test_m3_integration.py -q
# 15 passed

python -m pytest tests/test_m3_ui.py -q
# 8 passed

python -m pytest backend/tests -q
# 141 passed

python -m pytest tests -q --ignore=tests/test_contextual_query.py \
  --ignore=tests/test_knowledge_contract.py --ignore=tests/test_live_rag_integration.py \
  --ignore=tests/test_m1.py --ignore=tests/test_retrieval_metadata.py
# 117 passed
```

`117 = 32 pre-existing passing tests (orchestrator + evaluation metrics) + 85
Milestone 3 tests`.

| ID | Case | Actual result | Status |
|---|---|---|---|
| TC-I-01 | Manual workflow | 2 customer + 1 agent messages, 2 analyses, 1 tone, turn 2 context 1 | PASS |
| TC-I-02 | Persistence/resume | Session file written; restored messages equal; resumed turn is customer turn 3 with 2 prior turns | PASS |
| TC-I-03 | Replay workflow | 6 messages, roles alternate, 3 analyses, 3 tone records | PASS |
| TC-I-04 | Report data | Frustration values and peak risk in 0–100 | PASS |
| TC-I-05 | Compatible outputs | Identical key sets/intent/sentiment/frustration/source | PASS |
| TC-I-06 | Agent history | `[customer(turn 1), agent(None)]` | PASS |
| TC-I-07 | Knowledge (both) | Stub chunk present in both Manual and Replay analyses | PASS |
| TC-I-08 | Escalation (both) | `requires_human_review=True`, `p2_high`, alert text in both | PASS |
| TC-I-09 | Replay coaching | 2 scored agent replies with notes | PASS |
| TC-I-10 | Replay persistence | Position 3 / paused / cache saved; continue to 4 with 2 analyses | PASS |
| TC-I-11 | Legacy session | Replay defaults applied, message preserved | PASS |
| TC-I-12 | Cross-mode isolation | Independent messages, counts, caches and intents | PASS |
| TC-I-13 | Simulator regression | `MODES` unchanged; persona messages differ; validation passes | PASS |
| TC-I-14 | Legacy parser | Correct role/text pairs | PASS |
| TC-I-15 | Setup validation | Manual valid, invalid without context, Replay needs ≥2 messages | PASS |
| TC-I-16 | Orchestrator | `status="completed"`, dict result | PASS |
| TC-I-17 | Intent agent | `AgentResult`, intent `order_or_service_status` | PASS |
| TC-I-18 | Existing suites | `backend/tests`: 141 passed. Root suite: 117 passed when the five pre-existing un-importable modules are excluded | PASS (with documented environment limitation) |
| TC-I-19 | UI Manual setup | `view=console`, config Manual, session JSON exists | PASS |
| TC-I-20 | UI Replay setup | Preview 7 rows; script length 7; format `txt`; conversation id `sample_transcript` | PASS |
| TC-I-21 | Three panels | Coaching Feed + Knowledge headings, Intent metric, escalation banner on angry replay | PASS |

## Regression detail

| Suite | Result |
|---|---|
| `backend/tests` (141 tests: data models, intent/emotion/context, agent contracts) | 141 passed |
| `tests/test_orchestrator.py` + `tests/test_evaluation_metrics.py` | 32 passed |
| Milestone 3 (`test_manual_mode`, `test_replay_mode`, `test_m3_integration`, `test_m3_ui`) | 85 passed |

### Pre-existing environment failure (not caused by Milestone 3)

Running `python -m pytest -q` from the repository root aborts collection with
five errors:

```
ERROR tests/test_contextual_query.py
ERROR tests/test_knowledge_contract.py
ERROR tests/test_live_rag_integration.py
ERROR tests/test_m1.py
ERROR tests/test_retrieval_metadata.py
google.protobuf.runtime_version.VersionError: Detected incompatible
Protobuf Gencode/Runtime versions when loading tensorflow/...
```

Cause: `backend/services/rag_stub.py` imports ChromaDB /
sentence-transformers, which pull TensorFlow with a Protobuf runtime older
than its generated code in this local Python environment. This was reproduced
**before** any Milestone 3 file was changed. Milestone 3 code does not import
ChromaDB and does not add to the problem. Fixing it requires reinstalling or
aligning `protobuf`/`tensorflow`/`chromadb` versions in the environment, which
is outside the assigned scope and was not attempted.

**No failures were hidden, skipped or converted to xfail.** Every result above
is from an actual executed run.
