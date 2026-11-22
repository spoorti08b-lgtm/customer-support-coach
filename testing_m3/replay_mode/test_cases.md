# Replay Mode — Test Cases

**Scope:** JSON/CSV/TXT upload and validation, parsing and speaker
identification, preview, replay controls, per-message AI processing, agent
message handling, context/sentiment updates, and prevention of duplicate
turns/analyses when navigating backwards.

Automated suite: `tests/test_replay_mode.py` (all parser/controller cases
below are automated). UI cases are in `tests/test_m3_ui.py`.

| ID | Case | Preconditions | Steps | Expected result | Automated test |
|---|---|---|---|---|---|
| TC-R-01 | JSON upload | `testing_m3/sample_transcripts/sample_transcript.json` | Parse file | 6 messages, 3 customer, conversation id `replay_001`, alternating roles | `test_json_transcript_upload` |
| TC-R-02 | CSV upload | `sample_transcript.csv` | Parse file | 5 messages, 3 customer, quoted commas preserved | `test_csv_transcript_upload` |
| TC-R-03 | TXT upload | `sample_transcript.txt` | Parse file | 7 messages, 4 customer, speaker/text split correctly | `test_txt_transcript_upload` |
| TC-R-04 | Speaker identification | Transcript with Client/Support agent/User labels | Parse | All mapped to customer/agent | `test_speaker_aliases_are_recognised` |
| TC-R-05 | Multi-line messages | TXT with an unlabelled continuation line | Parse | Continuation appended to previous message; 2 messages | `test_unlabelled_lines_continue_the_previous_message` |
| TC-R-06 | Chronological ordering | JSON sample | Parse | Indexes 1..6 and ids `msg-0001..0006` in file order | `test_chronological_ordering_is_preserved` |
| TC-R-07 | Transcript preview | CSV sample | Build preview rows | `#`, Speaker, Message per row; row count equals message count | `test_transcript_preview_rows`, UI TC-R-20 |
| TC-R-08 | Missing speaker | JSON message without speaker | Parse | Rejected with "missing a speaker label" | `test_missing_speaker_is_rejected` |
| TC-R-09 | Unknown speaker | TXT starting with `Robot:` | Parse | Rejected with "unrecognised speaker" | `test_unknown_speaker_is_rejected` |
| TC-R-10 | Unknown speaker mid-file | `Robot:` after a customer message | Parse | Treated as continuation with a warning; 2 messages | `test_unrecognised_speaker_mid_file_is_kept_as_continuation` |
| TC-R-11 | Malformed JSON | Truncated JSON | Parse | Rejected with "not valid JSON" and line/column | `test_malformed_json_is_rejected` |
| TC-R-12 | CSV without required headers | Header `a,b` | Parse | Rejected: needs speaker + message columns | `test_csv_without_required_headers_is_rejected` |
| TC-R-13 | Empty file | 0 bytes | Parse | Rejected "empty" | `test_empty_file_is_rejected` |
| TC-R-14 | Unsupported file type | `.pdf` upload | Parse | Rejected "Unsupported transcript file type" | `test_unsupported_file_type_is_rejected` |
| TC-R-15 | Oversized file | Content > 2 MB | Parse | Rejected "too large" with limit | `test_oversized_transcript_is_rejected` |
| TC-R-16 | Single message | One customer line | Parse | Rejected "at least 2 messages" | `test_single_message_transcript_is_rejected` |
| TC-R-17 | No customer messages | Agent-only transcript | Parse | Rejected "no customer messages" | `test_transcript_without_customer_messages_is_rejected` |
| TC-R-18 | Empty messages | JSON with a blank message | Parse | Blank skipped with warning; remaining messages kept | `test_empty_messages_are_skipped_with_a_warning` |
| TC-R-19 | Initial replay state | 6-message transcript | Initialise | Position 0, total 6, status `idle`, progress 0, current message 1, not finished | `test_replay_initial_state` |
| TC-R-20 | Setup preview + start | App running | Select Replay, keep bundled sample, start session | Preview table with 7 rows, conversation id + format captions, session stores 7-message script | `test_setup_previews_and_starts_bundled_replay` (UI) |
| TC-R-21 | Upload required | App running | Select Replay → Upload file, no file, start | Blocked on setup page with transcript error | `test_setup_blocks_replay_without_a_transcript` (UI) |
| TC-R-22 | Next message | Replay session at 0 | Next | Position 1, one message, one analysis, id `msg-0001` | `test_next_message_adds_one_turn_at_a_time` |
| TC-R-23 | Start / Pause / Resume | Replay session | Start, pause, resume, auto-advance | Status transitions playing → paused → playing; pause blocks advancing | `test_start_pause_resume_and_auto_advance` |
| TC-R-24 | Previous message | 4 messages played | Previous twice | Position 2, 2 messages, 1 analysis, 1 tone; roles customer/agent | `test_previous_message_never_duplicates_turns_or_analyses` |
| TC-R-25 | Forward again after rewind | Same session | Next twice | Position/message/analysis counts return to 4/4/2 (no duplicates) | `test_previous_message_never_duplicates_turns_or_analyses` |
| TC-R-26 | Duplicate processing prevention | Counter around the analyser | Play 5, rewind 2, play 3 | Analyser called exactly 3 times (cache reused) | `test_rewind_reuses_cached_analyses` |
| TC-R-27 | Restart | 3 messages played | Restart | Position 0, status idle, conversation/analyses/tones empty | `test_restart_clears_visible_conversation` |
| TC-R-28 | Restart reuses cache | Counter around the analyser | Play 4, restart, play 4 | No additional analyser calls | `test_restart_then_replay_reuses_analyses` |
| TC-R-29 | Customer vs agent handling | 2-message script | Play customer + agent | 1 analysis, 1 scored tone; agent message kept in conversation | `test_agent_messages_are_not_analysed_as_customer` |
| TC-R-30 | Context + trajectory during replay | 4-message script | Play 3 | Latest analysis has 1 prior customer turn and ≥2 trajectory points | `test_replay_context_and_sentiment_trajectory_update` |
| TC-R-31 | Finish state | 6-message transcript | Next until end | Position = total = 6, finished, status `finished`, no current message; Start rewinds to 0 and plays | `test_replay_reaches_finished_state_at_the_end` |
| TC-R-32 | Position bounds | Replay session | `go_to(-5)`, `go_to(99)` | Clamped to 0 and 6 | `test_go_to_is_clamped_to_the_transcript` |
| TC-R-33 | Invalid script speaker | Script role `robot` | Initialise | Clear `ValueError` (unsupported speaker), never silently reclassified | `test_invalid_speaker_in_script_is_rejected` |
| TC-R-34 | Cache reset on new transcript | 3 messages played, init reset | Reset | Caches emptied, conversation cleared, position 0 | `test_init_reset_clears_old_transcript_cache` |
| TC-R-35 | Console Next/Previous/Restart | Console seeded, Replay | Three Next, Previous, Next ×2, Restart | Counts 3/3/2 → 2/2/1 → 4/4/2 → 0/0/0; controls all present | `test_replay_console_next_previous_restart` (UI) |
| TC-R-36 | Finish + escalation in console | Angry customer in script | Next ×3 | Status finished, 2 analyses, escalation error banner, "End of transcript" notice | `test_replay_console_finishes_and_alerts_on_escalation` (UI) |

**Edge cases from the brief and their coverage:** empty file (TC-R-13),
unsupported type (TC-R-14), malformed transcript (TC-R-08/09/11/12),
missing speaker (TC-R-08/09), empty messages (TC-R-18), duplicate processing
prevention (TC-R-26/28), backward navigation (TC-R-24/25), agent messages
(TC-R-29), context retention (TC-R-30).
