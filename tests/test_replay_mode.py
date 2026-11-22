"""Replay Mode tests (Milestone 3).

Two layers are covered:

* transcript upload validation and parsing for JSON, CSV and TXT;
* the replay controller - start/pause/resume/next/previous/restart, with
  cached analyses so moving backwards and forwards never duplicates turns
  or analysis records.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.modes import coaching, replay, transcripts

PRODUCT = "Acme Wireless Router X200"
SCENARIO = "Customer reports a delayed order and repeated unresolved contacts."
SAMPLE_DIR = (
    Path(__file__).resolve().parent.parent / "testing_m3" / "sample_transcripts"
)


def read_sample(name: str) -> bytes:
    return (SAMPLE_DIR / name).read_bytes()


def make_session(script: list[dict] | None = None, **config) -> dict:
    return {
        "sid": "replay01",
        "config": {
            "mode": "Replay",
            "product": PRODUCT,
            "scenario": SCENARIO,
            "persona": "Calm",
            "max_turns": 5,
            "replay_script": script or [],
            **config,
        },
        "messages": [],
        "analyses": [],
        "tone": [],
        "replay_idx": 0,
        "replay_status": "idle",
        "replay_analyses": {},
        "replay_tones": {},
    }


def json_session() -> dict:
    transcript = transcripts.parse_transcript_bytes(
        "sample_transcript.json", read_sample("sample_transcript.json")
    )
    return make_session(transcript.script())


def two_turn_session() -> dict:
    return make_session(
        [
            {"role": "customer", "text": "My order has not arrived yet."},
            {"role": "agent", "text": "I'm sorry, let me check the tracking."},
            {"role": "customer", "text": "I have contacted support twice. This is ridiculous!"},
            {"role": "agent", "text": "I understand. I'm escalating this now."},
        ]
    )


# ---------------------------------------------------------------------------
# Transcript upload and parsing
# ---------------------------------------------------------------------------


def test_json_transcript_upload():
    transcript = transcripts.parse_transcript_bytes(
        "sample_transcript.json", read_sample("sample_transcript.json")
    )

    assert transcript.conversation_id == "replay_001"
    assert transcript.source_format == "json"
    assert transcript.total == 6
    assert transcript.customer_count == 3
    assert [m.role for m in transcript.messages] == [
        "customer",
        "agent",
        "customer",
        "agent",
        "customer",
        "agent",
    ]
    assert transcript.messages[0].text.startswith("My order ACM-4521")
    assert transcript.messages[-1].text.startswith("I'm escalating")


def test_csv_transcript_upload():
    transcript = transcripts.parse_transcript_bytes(
        "sample_transcript.csv", read_sample("sample_transcript.csv")
    )

    assert transcript.source_format == "csv"
    assert transcript.total == 5
    assert transcript.customer_count == 3
    # Quoted commas must survive CSV parsing.
    assert "ACME-89412" in transcript.messages[0].text


def test_txt_transcript_upload():
    transcript = transcripts.parse_transcript_bytes(
        "sample_transcript.txt", read_sample("sample_transcript.txt")
    )

    assert transcript.source_format == "txt"
    assert transcript.total == 7
    assert transcript.customer_count == 4
    assert transcript.messages[2].role == "customer"
    assert transcript.messages[2].text.startswith("It says my password is locked")


def test_speaker_aliases_are_recognised():
    raw = b"Client: My parcel is late.\nSupport agent: I'm sorry, let me check.\nUser: Thanks."
    transcript = transcripts.parse_transcript_bytes("aliases.txt", raw)

    assert [m.role for m in transcript.messages] == ["customer", "agent", "customer"]


def test_unlabelled_lines_continue_the_previous_message():
    raw = b"Customer: My order is late.\nIt was due on Monday.\nAgent: Sorry about that."
    transcript = transcripts.parse_transcript_bytes("multiline.txt", raw)

    assert transcript.total == 2
    assert transcript.messages[0].text == "My order is late. It was due on Monday."


def test_chronological_ordering_is_preserved():
    transcript = transcripts.parse_transcript_bytes(
        "sample_transcript.json", read_sample("sample_transcript.json")
    )

    assert [m.index for m in transcript.messages] == [1, 2, 3, 4, 5, 6]
    assert [m.id for m in transcript.messages] == [
        f"msg-{i:04d}" for i in range(1, 7)
    ]


def test_transcript_preview_rows():
    transcript = transcripts.parse_transcript_bytes(
        "sample_transcript.csv", read_sample("sample_transcript.csv")
    )

    rows = transcript.preview_rows()
    assert rows[0]["#"] == 1
    assert rows[0]["Speaker"] == "Customer"
    assert len(rows) == transcript.total


def test_missing_speaker_is_rejected():
    raw = json.dumps({"messages": [{"message": "No speaker here"}]}).encode()

    with pytest.raises(transcripts.TranscriptError, match="missing a speaker"):
        transcripts.parse_transcript_bytes("bad.json", raw)


def test_unknown_speaker_is_rejected():
    raw = b"Robot: I am not a support agent\nCustomer: hi"

    with pytest.raises(transcripts.TranscriptError, match="unrecognised speaker"):
        transcripts.parse_transcript_bytes("bad.txt", raw)


def test_unrecognised_speaker_mid_file_is_kept_as_continuation():
    raw = b"Customer: hello\nRobot: I am not a support agent\nAgent: hi"

    transcript = transcripts.parse_transcript_bytes("odd.txt", raw)

    assert transcript.total == 2
    assert "I am not a support agent" in transcript.messages[0].text
    assert transcript.warnings


def test_malformed_json_is_rejected():
    with pytest.raises(transcripts.TranscriptError, match="not valid JSON"):
        transcripts.parse_transcript_bytes("bad.json", b'{"messages": [')


def test_csv_without_required_headers_is_rejected():
    with pytest.raises(transcripts.TranscriptError, match="header row"):
        transcripts.parse_transcript_bytes("bad.csv", b"a,b\n1,2\n3,4\n")


def test_empty_file_is_rejected():
    with pytest.raises(transcripts.TranscriptError, match="empty"):
        transcripts.parse_transcript_bytes("empty.txt", b"")


def test_unsupported_file_type_is_rejected():
    with pytest.raises(transcripts.TranscriptError, match="Unsupported"):
        transcripts.parse_transcript_bytes("transcript.pdf", b"%PDF-1.4")


def test_oversized_transcript_is_rejected():
    raw = b"x" * (transcripts.MAX_TRANSCRIPT_BYTES + 1)

    with pytest.raises(transcripts.TranscriptError, match="too large"):
        transcripts.parse_transcript_bytes("huge.txt", raw)


def test_single_message_transcript_is_rejected():
    with pytest.raises(transcripts.TranscriptError, match="at least 2 messages"):
        transcripts.parse_transcript_bytes("one.txt", b"Customer: hello")


def test_transcript_without_customer_messages_is_rejected():
    raw = b"Agent: hello\nAgent: anyone there?"

    with pytest.raises(transcripts.TranscriptError, match="no customer messages"):
        transcripts.parse_transcript_bytes("agent.txt", raw)


def test_empty_messages_are_skipped_with_a_warning():
    raw = b'{"messages": [{"speaker": "customer", "message": "Help"},\n{"speaker": "agent", "message": "   "},\n{"speaker": "agent", "message": "Hello, how can I help?"}]}'

    transcript = transcripts.parse_transcript_bytes("sparse.json", raw)

    assert transcript.total == 2
    assert any("empty" in warning for warning in transcript.warnings)


# ---------------------------------------------------------------------------
# Replay controls
# ---------------------------------------------------------------------------


def test_replay_initial_state():
    session = json_session()

    state = replay.init_state(session, reset=True)

    assert state == {
        "position": 0,
        "total": 6,
        "status": "idle",
        "progress": 0.0,
        "current": {
            "index": 1,
            "id": "msg-0001",
            "role": "customer",
            "text": (
                "My order ACM-4521 has not arrived and it was due three days ago."
            ),
        },
        "finished": False,
        "has_script": True,
    }


def test_next_message_adds_one_turn_at_a_time():
    session = json_session()
    replay.init_state(session, reset=True)

    state = replay.next_message(session)

    assert state["position"] == 1
    assert len(session["messages"]) == 1
    assert len(session["analyses"]) == 1
    assert session["messages"][0]["id"] == "msg-0001"


def test_start_pause_resume_and_auto_advance():
    session = json_session()
    replay.init_state(session, reset=True)

    assert replay.start(session)["status"] == "playing"
    assert replay.pause(session)["status"] == "paused"
    assert replay.resume(session)["status"] == "playing"

    replay.auto_advance(session)
    assert session["replay_idx"] == 1
    assert replay.state(session)["status"] == "playing"

    replay.pause(session)
    replay.auto_advance(session)
    assert session["replay_idx"] == 1, "paused replay must not advance"


def test_previous_message_never_duplicates_turns_or_analyses():
    session = json_session()
    replay.init_state(session, reset=True)
    for _ in range(4):
        replay.next_message(session)

    assert session["replay_idx"] == 4
    assert len(session["messages"]) == 4
    assert len(session["analyses"]) == 2

    replay.previous_message(session)
    replay.previous_message(session)

    assert session["replay_idx"] == 2
    assert len(session["messages"]) == 2
    assert len(session["analyses"]) == 1
    assert len(session["tone"]) == 1
    assert [m["role"] for m in session["messages"]] == ["customer", "agent"]

    for _ in range(2):
        replay.next_message(session)

    assert session["replay_idx"] == 4
    assert len(session["messages"]) == 4
    assert len(session["analyses"]) == 2


def test_rewind_reuses_cached_analyses(monkeypatch):
    calls = {"count": 0}
    original = coaching.analyze_customer_turn

    def counting(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(coaching, "analyze_customer_turn", counting)

    session = json_session()
    replay.init_state(session, reset=True)
    for _ in range(5):
        replay.next_message(session)
    analysed_once = calls["count"]
    assert analysed_once == 3

    replay.previous_message(session)
    replay.previous_message(session)
    replay.next_message(session)
    replay.next_message(session)
    replay.next_message(session)

    assert calls["count"] == analysed_once, (
        "replaying a message must reuse its cached analysis"
    )


def test_restart_clears_visible_conversation():
    session = json_session()
    replay.init_state(session, reset=True)
    for _ in range(3):
        replay.next_message(session)

    state = replay.restart(session)

    assert state["position"] == 0
    assert state["status"] == "idle"
    assert session["messages"] == []
    assert session["analyses"] == []
    assert session["tone"] == []


def test_restart_then_replay_reuses_analyses(monkeypatch):
    calls = {"count": 0}
    original = coaching.analyze_customer_turn

    def counting(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(coaching, "analyze_customer_turn", counting)

    session = json_session()
    replay.init_state(session, reset=True)
    for _ in range(4):
        replay.next_message(session)
    before = calls["count"]

    replay.restart(session)
    for _ in range(4):
        replay.next_message(session)

    assert calls["count"] == before


def test_agent_messages_are_not_analysed_as_customer():
    session = two_turn_session()
    replay.init_state(session, reset=True)
    replay.next_message(session)
    replay.next_message(session)

    assert [m["role"] for m in session["messages"]] == ["customer", "agent"]
    assert len(session["analyses"]) == 1
    assert len(session["tone"]) == 1
    assert session["tone"][0]["score"] is not None


def test_replay_context_and_sentiment_trajectory_update():
    session = two_turn_session()
    replay.init_state(session, reset=True)
    for _ in range(3):
        replay.next_message(session)

    latest = session["analyses"][-1]
    assert latest["conversation_context"]["customer_turns"] == 1
    assert len(latest["sentiment_trajectory"]) >= 2
    assert latest["sentiment_trend"] in {"unknown", "stable", "improving", "worsening"}


def test_replay_reaches_finished_state_at_the_end():
    session = json_session()
    replay.init_state(session, reset=True)

    for _ in range(6):
        replay.next_message(session)

    state = replay.state(session)
    assert state["position"] == state["total"] == 6
    assert state["finished"]
    assert state["status"] == "finished"
    assert state["current"] is None
    assert replay.start(session)["position"] == 0

    # Starting again rewinds and plays.
    assert replay.state(session)["status"] == "playing"


def test_go_to_is_clamped_to_the_transcript():
    session = json_session()
    replay.init_state(session, reset=True)

    assert replay.go_to(session, -5)["position"] == 0
    assert replay.go_to(session, 99)["position"] == 6


def test_invalid_speaker_in_script_is_rejected():
    session = make_session([{"role": "robot", "text": "hello"}])

    with pytest.raises(ValueError, match="unsupported"):
        replay.init_state(session, reset=True)


def test_init_reset_clears_old_transcript_cache():
    session = json_session()
    replay.init_state(session, reset=True)
    for _ in range(3):
        replay.next_message(session)

    replay.init_state(session, reset=True)

    assert session["replay_analyses"] == {}
    assert session["replay_tones"] == {}
    assert session["messages"] == []
    assert session["replay_idx"] == 0
