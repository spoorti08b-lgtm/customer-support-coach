# Manual Mode — Test Cases

**Scope:** creating a Manual session, submitting pasted customer messages,
multi-turn context, agent analysis (intent, sentiment, emotion, frustration,
trend), knowledge retrieval, coaching, escalation, validation, duplicate
prevention and session isolation.

Automated suite: `tests/test_manual_mode.py` (all cases below are automated).

| ID | Case | Preconditions | Steps | Expected result | Automated test |
|---|---|---|---|---|---|
| TC-M-01 | Manual session creation | App running | Select Manual on setup, enter product + scenario, start session | Session created with unique id, Manual config, empty conversation | `test_manual_session_creation`, `test_setup_starts_manual_session` (UI) |
| TC-M-02 | Valid customer message submission | Manual session | Paste "My order has not arrived yet." and submit | Message stored with id `msg-0001`, role `customer`, one analysis | `test_manual_session_creation` |
| TC-M-03 | Empty message rejected | Manual session | Submit "" / whitespace / newlines | Validation error, no message or analysis stored | `test_empty_message_is_rejected` (3 params) |
| TC-M-04 | Long message rejected | Manual session | Submit 1501 characters | "too long" error, nothing stored | `test_long_message_is_rejected` |
| TC-M-05 | Message at the limit accepted | Manual session | Submit exactly 1500 characters | Accepted and analysed | `test_message_at_the_limit_is_accepted` |
| TC-M-06 | Invalid session id | Missing, empty, path-like, spaced or non-string id | Submit a message | Session-specific error, `invalid_session=True`, nothing stored | `test_invalid_session_id_is_rejected` (5 params) |
| TC-M-07 | Wrong mode rejected | Session config is Replay | Submit via Manual path | "Manual Mode is not active" error, nothing stored | `test_wrong_mode_is_rejected` |
| TC-M-08 | Multiple messages retained | Manual session | Submit message, agent reply, second message | 3 messages in order with ids `msg-0001..0003` | `test_multiple_messages_and_context_retention` |
| TC-M-09 | Context retention across turns | Manual session | Two customer turns with an agent reply between | Second analysis turn 2, `conversation_context.customer_turns == 1` | `test_multiple_messages_and_context_retention` |
| TC-M-10 | Agent reply scored, not classified as customer | Manual session | Submit an agent reply | Tone score 0–100 with notes; no customer analysis added | `test_agent_reply_is_scored_and_not_analysed_as_customer` |
| TC-M-11 | Duplicate submission prevented | Manual session, one message sent | Resubmit same text with extra/case-changed whitespace | "already submitted" error; still 1 message and 1 analysis | `test_duplicate_customer_submission_is_prevented` |
| TC-M-12 | Legitimate repeat after agent reply | Manual session | Repeat same customer text after an agent reply | Accepted as a new turn | `test_customer_may_repeat_after_agent_reply` |
| TC-M-13 | Duplicate agent reply prevented | Manual session | Send same reply twice | Second reply rejected as duplicate | `test_duplicate_agent_reply_is_prevented` |
| TC-M-14 | Session isolation | Two Manual sessions | Send a message in each | Message counts, analysis lists and intents stay per session | `test_sessions_are_isolated` |
| TC-M-15 | Multiple concurrent sessions | Two sessions | Interleave two turns in each | Each keeps its own 2 customer turns and context count 1 | `test_multiple_concurrent_sessions_keep_their_own_context` |
| TC-M-16 | Intent analysis | Manual session | Submit duplicate-charge message | Intent `billing_or_payment` ("Billing or payment"), confidence 0–1, source `intent_sentiment_agent` | `test_intent_detection` |
| TC-M-17 | Emotion detection | Manual session | Submit "broken again / unacceptable / furious" | Emotions include Anger and Frustration; primary emotion Frustration | `test_emotion_detection` |
| TC-M-18 | Frustration classification | Manual session | Same angry message | 0–100 score, level in none/low/moderate/high/severe and not `none` | `test_frustration_classification` |
| TC-M-19 | Sentiment trajectory recorded | Manual session | Three customer turns with changing tone | ≥2 trajectory points, trend in improving/stable/worsening, context count 2 | `test_sentiment_trajectory_is_recorded` |
| TC-M-20 | Worsening sentiment detected | Manual session | positive → positive → angry → negative turns | Trend `worsening` | `test_sentiment_worsening_is_detected` |
| TC-M-21 | Knowledge retrieval integration | Knowledge lookup stubbed | Submit a message | Retrieved chunk appears in analysis and in the suggested response text | `test_knowledge_retrieval_flows_into_the_analysis` |
| TC-M-22 | Coaching suggestions | Manual session | Submit a frustrated message | Coaching focus, guidance, suggested response and strategy all non-empty | `test_coaching_suggestions_are_produced` |
| TC-M-23 | Escalation integration | Manual session | Submit a legal-threat/churn message | `requires_human_review`, priority `p2_high`, signals, risk reason, alert text | `test_escalation_integration` |
| TC-M-24 | Escalation alert threshold | Analysis dicts | Evaluate low-risk, high-risk and missing analyses | Low → no alert; high → alert with priority label; None → no alert | `test_escalation_alert_threshold` |
| TC-M-25 | Agent unavailable (API error) | `analyze_message` raises | Submit a message | Turn still succeeds via flagged rule-based fallback; error recorded; no invented agent output | `test_agent_failure_falls_back_without_inventing_output` |
| TC-M-26 | Analysis failure reported | Analysis call raises | Submit a message | Message kept, no analysis record, explicit "Coaching analysis failed" error | `test_analysis_error_is_reported_and_message_kept` |
| TC-M-27 | Reply evaluation failure | Tone helper raises | Evaluate a reply | Score `None`, notes and error present (no fake score) | `test_agent_reply_evaluation_failure_is_reported` |
| TC-M-28 | Console message form + panels | Console seeded, Manual | Paste a message, click "Add message and coach" | Chat bubble appears, Intent/Sentiment metrics populate, Coaching Feed and Knowledge panels render, success flash | `test_manual_console_submits_message_and_updates_panels` (UI) |
| TC-M-29 | Console rejects empty/duplicate | Console seeded, Manual | Submit empty, then a message, then the same message | Error for empty; one message only; duplicate warning | `test_manual_console_rejects_empty_and_duplicate_messages` (UI) |
| TC-M-30 | Console records agent reply | Console seeded, Manual | Submit customer message, then reply | Messages `[customer, agent]`, one tone record with score | `test_manual_console_records_agent_reply` (UI) |

**Edge cases from the brief and their coverage:** empty messages (TC-M-03),
invalid session ids (TC-M-06), duplicate submissions (TC-M-11, TC-M-13),
long messages (TC-M-04/05), API errors (TC-M-25/26/27), missing context
(TC-M-01 setup validation, TC-M-06), multiple concurrent sessions
(TC-M-15), session isolation (TC-M-14).
