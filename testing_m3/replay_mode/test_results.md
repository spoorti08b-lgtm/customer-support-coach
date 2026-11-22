# Replay Mode — Test Results

**Executed:** 2026-11-22
**Environment:** Windows, Python 3.11.5, Streamlit 1.38.0, pydantic 2.9.2,
pytest 8.3.3
**Command:**

```bash
python -m pytest tests/test_replay_mode.py tests/test_m3_ui.py -q
```

**Outcome:** `39 passed` (31 Replay core tests + 8 UI tests, of which 5 are
Replay-related).

| ID | Case | Actual result | Status |
|---|---|---|---|
| TC-R-01 | JSON upload | 6 messages, 3 customer, id `replay_001`, roles alternate | PASS |
| TC-R-02 | CSV upload | 5 messages, 3 customer, `ACME-89412` intact inside quoted field | PASS |
| TC-R-03 | TXT upload | 7 messages, 4 customer, password message at index 3 | PASS |
| TC-R-04 | Speaker aliases | Client→customer, Support agent→agent, User→customer | PASS |
| TC-R-05 | Multi-line TEXT | 2 messages; first text "My order is late. It was due on Monday." | PASS |
| TC-R-06 | Ordering | Indexes 1–6, ids `msg-0001`–`msg-0006` | PASS |
| TC-R-07 | Preview rows | 5 rows for the CSV sample, `#`/Speaker/Message columns | PASS |
| TC-R-08 | Missing speaker | "JSON message 1 is missing a speaker label ('speaker' or 'role')." | PASS |
| TC-R-09 | Unknown speaker | "The first line has an unrecognised speaker ('Robot')." | PASS |
| TC-R-10 | Unknown speaker mid-file | Kept as continuation, warning recorded, 2 messages | PASS |
| TC-R-11 | Malformed JSON | "The JSON transcript is not valid JSON (line 1…)" | PASS |
| TC-R-12 | CSV headers | "needs a header row with a speaker column… and a message column" | PASS |
| TC-R-13 | Empty file | "The transcript file is empty." | PASS |
| TC-R-14 | Unsupported type | "Unsupported transcript file type…" | PASS |
| TC-R-15 | Oversized | "too large … limit is 2 MB" | PASS |
| TC-R-16 | Single message | "needs at least 2 messages to replay (found 1)" | PASS |
| TC-R-17 | No customer | "no customer messages" | PASS |
| TC-R-18 | Empty message | 2 messages kept, warning "Message 2 was empty and has been skipped." | PASS |
| TC-R-19 | Initial state | position 0 / total 6 / idle / progress 0.0 / current msg-0001 | PASS |
| TC-R-20 | Setup preview + start | Preview dataframe has 7 rows; captions show conversation id/format; script persisted with 7 messages, format `txt` | PASS |
| TC-R-21 | Upload required | Stayed on setup page; error mentions transcript | PASS |
| TC-R-22 | Next | Position 1, one message, one analysis | PASS |
| TC-R-23 | Start/pause/resume | playing → paused → playing; paused auto-advance did not move position | PASS |
| TC-R-24 | Previous | Position 4→2, messages 4→2, analyses 2→1, tone 1 | PASS |
| TC-R-25 | Forward again | Returned to 4/4/2 with no duplicate records | PASS |
| TC-R-26 | Cache reuse | 3 analyser calls for 5 messages, unchanged after rewind/replay | PASS |
| TC-R-27 | Restart | Position 0, idle, all lists empty | PASS |
| TC-R-28 | Restart cache | Zero extra analyser calls on replay | PASS |
| TC-R-29 | Customer vs agent | 1 analysis and 1 tone for a customer+agent pair | PASS |
| TC-R-30 | Context/trajectory | Prior customer turns 1, trajectory ≥2 points, trend valid | PASS |
| TC-R-31 | Finish | position = total = 6, status finished, current `None`; Start rewinds to 0 and plays | PASS |
| TC-R-32 | Bounds | Clamped to 0 and 6 | PASS |
| TC-R-33 | Invalid script speaker | `ValueError: … unsupported speaker ('robot')` | PASS |
| TC-R-34 | Cache reset | Caches `{}`, messages `[]`, position 0 | PASS |
| TC-R-35 | Console controls | Buttons available: Previous, Next, Start, Pause, Resume, Restart; counts 3/3/2 → 2/2/1 → 4/4/2 → 0/0/0 | PASS |
| TC-R-36 | Finish + escalation | Finished status, 2 analyses, HIGH ESCALATION RISK banner, "End of transcript" notice | PASS |

**Notes**

- Rewind/forward navigation rebuilds the visible conversation as
  `transcript[:position]` and reuses cached analyses, which is why no duplicate
  turns or analysis records are created. This is asserted with a call counter,
  not just message counts (TC-R-26/28).
- Transcript messages are committed one at a time by "Next message"; the
  message about to be played is shown above the conversation window. This
  matches the "current position / total" display and keeps analysis tied to a
  committed turn.
- No test was skipped or weakened. All transcript fixtures are real files in
  `testing_m3/sample_transcripts/`.
