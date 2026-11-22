# Integration & Regression — Test Cases

**Scope:** both modes wired to conversation management, the agent pipeline,
knowledge, coaching and escalation; context and session isolation; complete
workflows; persistence; Simulator Mode and orchestrator regressions.

Automated suite: `tests/test_m3_integration.py` (15 tests) plus the
cross-mode UI tests in `tests/test_m3_ui.py`.

| ID | Case | Preconditions | Steps | Expected result | Automated test |
|---|---|---|---|---|---|
| TC-I-01 | Manual Mode → conversation manager | Manual session | Submit two customer turns with one agent reply | Messages/analyses/tones counts and order correct; ids sequential | `test_complete_manual_mode_workflow` |
| TC-I-02 | Manual Mode → persistence → resume | Manual session saved | Save, load, continue conversation | Restored messages match; new turn is customer turn 3 with 2 prior turns | `test_complete_manual_mode_workflow` |
| TC-I-03 | Replay Mode → conversation manager | 6-message JSON transcript | Play to the end | 6 messages alternating, 3 analyses, 3 tone records | `test_complete_replay_mode_workflow` |
| TC-I-04 | Replay report compatibility | Finished replay | Read frustration list and peak risk | All values in 0–100 range (report page fields) | `test_complete_replay_mode_workflow` |
| TC-I-05 | Both modes → same orchestration path | Manual and Replay sessions | Analyse identical message | Identical key sets, intent, sentiment, frustration and source | `test_both_modes_produce_compatible_analyses` |
| TC-I-06 | Agent history normalisation | Replay played 3 messages | Inspect history given to the agent | Speakers `[customer, agent]`; only the customer turn is numbered | `test_replay_agent_turns_are_part_of_the_context` |
| TC-I-07 | Knowledge recommendation integration (both modes) | Retrieval stubbed | Submit/play a message in each mode | Same retrieved chunk appears in both analyses | `test_knowledge_recommendations_in_both_modes` |
| TC-I-08 | Escalation integration (both modes) | Angry legal-threat message | Analyse in Manual and Replay | `requires_human_review`, priority `p2_high`, alert message from both | `test_escalation_monitor_in_both_modes` |
| TC-I-09 | Coaching feedback for replay agent turns | 4-message transcript | Play 4 messages | Two agent turns scored with notes | `test_coaching_feedback_for_agent_replies_is_available_in_replay` |
| TC-I-10 | Replay state persistence | Replay at position 3 | Save, load, next | Position 3, status paused, cached analyses present; next → position 4 | `test_replay_state_survives_storage_round_trip` |
| TC-I-11 | Legacy session compatibility | Saved JSON without replay keys | Load | Defaults filled (`idle`, `{}`, `{}`); messages preserved | `test_legacy_saved_session_gets_replay_defaults` |
| TC-I-12 | Session isolation across modes | One Manual + one Replay session | Use both | Message lists, analysis counts and caches independent | `test_two_modes_stay_isolated` |
| TC-I-13 | Simulator regression | Simulator config | Generate turns and validate setup | `MODES` unchanged, persona-specific messages, setup validation passes | `test_simulator_mode_helpers_are_unchanged` |
| TC-I-14 | Legacy TXT parser regression | Raw TXT | `validation.parse_transcript` | Still returns `[{"role","text"}]` pairs | `test_legacy_transcript_parser_still_works` |
| TC-I-15 | Setup validation regression | Manual/Replay | Validate valid and invalid setups | Manual valid; missing context invalid; Replay without transcript invalid; Replay with 2 messages valid | `test_manual_and_replay_setup_validation` |
| TC-I-16 | Orchestrator regression | Mock session manager + agent | `run_workflow` | Status `completed`, non-empty result | `test_existing_orchestrator_workflow_still_completes` |
| TC-I-17 | Intent agent regression | Mock session | `IntentSentimentAgent().run` | Returns `AgentResult` with intent `order_or_service_status` | `test_intent_agent_still_returns_agent_result` |
| TC-I-18 | Existing test suites | — | Run `backend/tests` and root `tests` | No new failures caused by Milestone 3 | see integration_results.md |
| TC-I-19 | Manual session creation through UI | App running | Setup form → Start | Session state `console`, config `Manual`, file on disk | `test_setup_starts_manual_session` (UI) |
| TC-I-20 | Replay session creation through UI | App running | Setup Replay (bundled) → Start | 7-message script + format/conversation metadata stored | `test_setup_previews_and_starts_bundled_replay` (UI) |
| TC-I-21 | Three-panel console preserved | Console seeded | Render coaching + knowledge panels | "Coaching Feed" and "Knowledge" headings with metrics and escalation banner | `test_manual_console_submits_message_and_updates_panels`, `test_replay_console_finishes_and_alerts_on_escalation` (UI) |

**Testing standard:** real integration paths are used. The only stub is the
knowledge-base lookup in TC-I-07/TC-M-21, because the ChromaDB RAG stack cannot
be imported in this environment; the fallback path is tested explicitly and
labelled.
