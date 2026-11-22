# Manual Mode — Test Results

**Executed:** 2026-11-22
**Environment:** Windows, Python 3.11.5, Streamlit 1.38.0, pydantic 2.9.2,
pytest 8.3.3
**Command:**

```bash
python -m pytest tests/test_manual_mode.py tests/test_m3_ui.py -q
```

**Outcome:** `39 passed` (31 core Manual tests + 8 UI tests, of which 3 are
Manual-console tests).

| ID | Case | Actual result | Status |
|---|---|---|---|
| TC-M-01 | Manual session creation | Session created, config mode `Manual`, unique sid, session JSON written | PASS |
| TC-M-02 | Valid message submission | Message stored as `msg-0001`, one analysis appended | PASS |
| TC-M-03 | Empty message rejected | `Customer message can't be empty.`; no records written | PASS |
| TC-M-04 | Long message rejected | `Customer message is too long (max 1500 characters).` | PASS |
| TC-M-05 | 1500-char message | Accepted and analysed | PASS |
| TC-M-06 | Invalid session id | Rejected with session-specific message for None, empty, `../escape`, `bad id`, `42` | PASS |
| TC-M-07 | Wrong mode | Rejected: "Manual Mode is not active for this session (mode: Replay)." | PASS |
| TC-M-08 | Multiple messages | 3 messages, roles customer/agent/customer, ids sequential | PASS |
| TC-M-09 | Context retention | Turn 2, prior customer turns 1, `has_context=True` | PASS |
| TC-M-10 | Agent reply | Tone score 100/100 for the sample reply; zero analyses added | PASS |
| TC-M-11 | Duplicate customer | Rejected as duplicate; counts stayed 1/1 | PASS |
| TC-M-12 | Repeat after reply | Accepted as a new turn (customer count 2) | PASS |
| TC-M-13 | Duplicate agent reply | Rejected (case/whitespace-insensitive comparison) | PASS |
| TC-M-14 | Session isolation | Distinct lists and distinct intents per session | PASS |
| TC-M-15 | Concurrent sessions | Each session kept 2 customer turns and context 1; second intent `account_access` | PASS |
| TC-M-16 | Intent analysis | `billing_or_payment`, human label "Billing or payment", source `intent_sentiment_agent` | PASS |
| TC-M-17 | Emotion detection | `["Frustration", "Anger"]`, primary Frustration | PASS |
| TC-M-18 | Frustration | Score 58, level `moderate` | PASS |
| TC-M-19 | Trajectory | 2+ points, trend reported, context count 2 | PASS |
| TC-M-20 | Worsening trend | `worsening` after positive → positive → angry → negative | PASS |
| TC-M-21 | Knowledge retrieval | Stubbed chunk appears in `chunks`; source filename appears in the suggestion | PASS |
| TC-M-22 | Coaching suggestions | Focus, guidance, suggestion and strategy populated | PASS |
| TC-M-23 | Escalation | `requires_human_review=True`, priority `p2_high`, alert text rendered | PASS |
| TC-M-24 | Alert threshold | 10% → no alert; 85% → alert with "P1 - Critical"; None → no alert | PASS |
| TC-M-25 | Agent unavailable | `source=pipeline_stub_fallback`, error "agent unavailable", analysis still usable | PASS |
| TC-M-26 | Analysis crash | Message kept, no analysis, error "Coaching analysis failed..." | PASS |
| TC-M-27 | Tone crash | `score=None`, notes + error present | PASS |
| TC-M-28 | Console form/panels | One chat bubble, Intent "Order or service status", Coaching Feed + Knowledge headings, success flash | PASS |
| TC-M-29 | Empty/duplicate in UI | Empty submit produced an error and no message; duplicate produced a warning and no second message | PASS |
| TC-M-30 | UI agent reply | Roles `[customer, agent]`, one scored tone record | PASS |

**Notes**

- No test was skipped, xfailed or weakened to make it pass.
- The rule-based fallback is only used when the real agent raises, and the
  analysis is explicitly labelled `pipeline_stub_fallback` with the error text
  (TC-M-25). It is never presented as agent output.
- Values quoted above (e.g. score 58, 100/100 tone) are the values observed in
  this run; tests assert behaviour (bands/keys/relations) rather than brittle
  exact scores where the agent is heuristic.
