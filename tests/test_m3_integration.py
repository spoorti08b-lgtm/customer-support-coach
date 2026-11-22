"""Milestone 3 integration and regression tests.

Covers the complete Manual and Replay workflows end to end (conversation
management -> Intent & Sentiment Analysis Agent -> knowledge retrieval ->
coaching/escalation -> persistence) and checks that Simulator Mode and the
existing orchestrator still behave as before.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.agents.intent_sentiment_agent import IntentSentimentAgent
from backend.core.data_models import AgentResult
from backend.modes import coaching, manual, replay, transcripts
from orchestrator.mock_components import MockAgent, MockSessionManager
from orchestrator.orchestrator import run_workflow
from orchestrator.schemas import WorkflowRequest
from utils import pipeline_stub, storage, validation

SAMPLE_DIR = (
    Path(__file__).resolve().parent.parent / "testing_m3" / "sample_transcripts"
)
PRODUCT = "Acme Wireless Router X200"
SCENARIO = "Customer reports a delayed order after two previous contacts."

CORE_KEYS = {
    "intent",
    "sentiment",
    "emotion",
    "frustration",
    "risk",
    "risk_reason",
    "strategy",
    "suggestion",
    "chunks",
}


def manual_session(sid: str = "integr01") -> dict:
    return {
        "sid": sid,
        "config": {
            "mode": "Manual",
            "product": PRODUCT,
            "scenario": SCENARIO,
            "persona": "Calm",
            "max_turns": 5,
            "replay_script": [],
        },
        "messages": [],
        "analyses": [],
        "tone": [],
        "replay_idx": 0,
        "replay_status": "idle",
        "replay_analyses": {},
        "replay_tones": {},
    }


def json_transcript() -> transcripts.Transcript:
    return transcripts.parse_transcript_bytes(
        "sample_transcript.json",
        (SAMPLE_DIR / "sample_transcript.json").read_bytes(),
    )


def replay_session(sid: str = "integr02") -> dict:
    transcript = json_transcript()
    session = manual_session(sid)
    session["config"].update(
        {
            "mode": "Replay",
            "replay_script": transcript.script(),
            "replay_conversation_id": transcript.conversation_id,
            "replay_source_format": transcript.source_format,
        }
    )
    replay.init_state(session, reset=True)
    return session


# ---------------------------------------------------------------------------
# Complete workflows
# ---------------------------------------------------------------------------


def test_complete_manual_mode_workflow(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DIR", tmp_path)
    session = manual_session()

    first = manual.submit_customer_message(
        session, "My order ACM-4521 has not arrived and it was due three days ago."
    )
    reply = manual.submit_agent_reply(
        session,
        "I'm sorry your order is late. I've checked the tracking and it is at the local depot.",
    )
    second = manual.submit_customer_message(
        session, "I have contacted support twice already. This is ridiculous!"
    )

    assert first.ok and reply.ok and second.ok
    assert manual.message_count(session, "customer") == 2
    assert manual.message_count(session, "agent") == 1
    assert len(session["analyses"]) == 2
    assert len(session["tone"]) == 1
    assert second.analysis["conversation_context"]["customer_turns"] == 1
    assert second.analysis["turn_number"] == 2
    assert CORE_KEYS <= set(second.analysis)

    # Session persistence and restore (the same path the UI uses).
    storage.save(session)
    saved = (tmp_path / f"{session['sid']}.json")
    assert saved.exists()

    restored = storage.load(session["sid"])
    assert restored is not None
    restored_session = {"sid": session["sid"], **restored}
    assert restored_session["messages"] == session["messages"]

    continued = manual.submit_customer_message(
        restored_session, "Can you tell me exactly when the refund will arrive?"
    )
    assert continued.ok
    assert manual.message_count(restored_session, "customer") == 3
    assert continued.analysis["conversation_context"]["customer_turns"] == 2


def test_complete_replay_mode_workflow():
    session = replay_session()

    state = replay.start(session)
    assert state["status"] == "playing"

    while not replay.state(session)["finished"]:
        replay.auto_advance(session)

    final = replay.state(session)
    assert final["position"] == final["total"] == 6
    assert [m["role"] for m in session["messages"]] == [
        "customer",
        "agent",
        "customer",
        "agent",
        "customer",
        "agent",
    ]
    assert len(session["analyses"]) == 3
    assert len(session["tone"]) == 3

    latest = session["analyses"][-1]
    assert CORE_KEYS <= set(latest)
    assert latest["conversation_context"]["customer_turns"] == 2

    # The post-session report reads these fields directly.
    frustration = [item["frustration"] for item in session["analyses"]]
    peak_risk = max(item["risk"] for item in session["analyses"])
    assert all(0 <= value <= 100 for value in frustration)
    assert 0 <= peak_risk <= 100


def test_both_modes_produce_compatible_analyses():
    message = "My order has not arrived yet. This is the third time I have contacted you!"

    manual_turn = manual.submit_customer_message(manual_session(), message)
    session = manual_session()
    session["config"]["mode"] = "Replay"
    session["config"]["replay_script"] = [
        {"role": "customer", "text": message}
    ]
    replay.init_state(session, reset=True)
    replay.next_message(session)

    manual_analysis = manual_turn.analysis
    replay_analysis = session["analyses"][0]

    assert CORE_KEYS <= set(manual_analysis)
    assert set(manual_analysis) == set(replay_analysis)
    assert manual_analysis["intent_label"] == replay_analysis["intent_label"]
    assert manual_analysis["sentiment"] == replay_analysis["sentiment"]
    assert manual_analysis["frustration"] == replay_analysis["frustration"]
    assert manual_analysis["source"] == replay_analysis["source"]


def test_replay_agent_turns_are_part_of_the_context():
    session = replay_session()
    for _ in range(3):
        replay.next_message(session)

    # 3 transcript messages -> only 2 belong to the customer.
    assert len(session["messages"]) == 3
    assert len(session["analyses"]) == 2
    assert session["analyses"][-1]["turn_number"] == 2
    assert session["messages"][1]["role"] == "agent"

    history = coaching._agent_history(session["messages"][:2])
    assert [item["speaker"] for item in history] == ["customer", "agent"]
    assert history[0]["turn_number"] == 1
    assert history[1]["turn_number"] is None


# ---------------------------------------------------------------------------
# Agent integration (knowledge, coaching, escalation)
# ---------------------------------------------------------------------------


def test_knowledge_recommendations_in_both_modes(monkeypatch):
    chunks = [
        {
            "source": "shipping_and_delivery.pdf",
            "page": 1,
            "text": "Delayed parcels are refunded after 10 business days.",
            "score": 2.1,
        }
    ]
    monkeypatch.setattr(coaching.rag_stub, "retrieve", lambda query, k=3: chunks)

    manual_turn = manual.submit_customer_message(
        manual_session(), "My order has not arrived yet."
    )
    session = replay_session()
    replay.next_message(session)

    assert manual_turn.analysis["chunks"] == chunks
    assert session["analyses"][0]["chunks"] == chunks


def test_escalation_monitor_in_both_modes():
    angry = (
        "This is the worst service ever! I'm furious and want to cancel my "
        "account. I will file a complaint and contact my lawyer!"
    )

    manual_turn = manual.submit_customer_message(manual_session(), angry)

    session = manual_session("integr03")
    session["config"]["mode"] = "Replay"
    session["config"]["replay_script"] = [{"role": "customer", "text": angry}]
    replay.init_state(session, reset=True)
    replay.next_message(session)

    for analysis in (manual_turn.analysis, session["analyses"][0]):
        assert analysis["requires_human_review"] is True
        assert analysis["escalation_priority"] == "p2_high"
        alert, text = coaching.escalation_alert(analysis)
        assert alert
        assert "HIGH ESCALATION RISK" in text


def test_coaching_feedback_for_agent_replies_is_available_in_replay():
    session = replay_session()
    for _ in range(4):
        replay.next_message(session)

    assert len(session["tone"]) == 2
    for tone in session["tone"]:
        assert tone["score"] is not None
        assert tone["notes"]


# ---------------------------------------------------------------------------
# Persistence and session isolation
# ---------------------------------------------------------------------------


def test_replay_state_survives_storage_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DIR", tmp_path)
    session = replay_session("integr04")
    for _ in range(3):
        replay.next_message(session)
    storage.save(session)

    restored = storage.load("integr04")
    assert restored is not None
    assert restored["replay_idx"] == 3
    assert restored["replay_status"] == "paused"
    assert restored["replay_analyses"]

    restored_session = {"sid": "integr04", **restored}
    replay.next_message(restored_session)

    assert restored_session["replay_idx"] == 4
    assert len(restored_session["messages"]) == 4
    assert len(restored_session["analyses"]) == 2


def test_legacy_saved_session_gets_replay_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DIR", tmp_path)
    legacy = {
        "view": "report",
        "config": {"mode": "Manual", "product": "Acme"},
        "messages": [{"role": "customer", "text": "Hello"}],
        "analyses": [],
        "tone": [],
        "replay_idx": 0,
        "saved_at": "2026-05-01 10:00",
    }
    (tmp_path / "legacy01.json").write_text(json.dumps(legacy), encoding="utf-8")

    restored = storage.load("legacy01")

    assert restored["replay_status"] == "idle"
    assert restored["replay_analyses"] == {}
    assert restored["replay_tones"] == {}
    assert restored["messages"][0]["text"] == "Hello"


def test_two_modes_stay_isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DIR", tmp_path)
    manual_one = manual_session("isolation1")
    replay_one = replay_session("isolation2")

    manual.submit_customer_message(manual_one, "My card was charged twice.")
    for _ in range(3):
        replay.next_message(replay_one)

    assert manual_one["messages"] != replay_one["messages"]
    assert len(manual_one["analyses"]) == 1
    assert len(replay_one["analyses"]) == 2
    assert manual_one["replay_analyses"] == {}
    assert replay_one["analyses"][0]["intent"] != manual_one["analyses"][0]["intent"]


# ---------------------------------------------------------------------------
# Simulator Mode and pipeline regressions
# ---------------------------------------------------------------------------


def test_simulator_mode_helpers_are_unchanged():
    assert validation.MODES == ("Simulator", "Manual", "Replay")

    config = {
        "mode": "Simulator",
        "product": PRODUCT,
        "scenario": SCENARIO,
        "persona": "Angry",
        "max_turns": 5,
    }
    first = pipeline_stub.simulate_customer(config, 0)
    second = pipeline_stub.simulate_customer(config, 1)

    assert PRODUCT in first
    assert first != second
    assert validation.validate_setup("Simulator", PRODUCT, SCENARIO, []) == []


def test_legacy_transcript_parser_still_works():
    parsed = validation.parse_transcript(
        "Customer: My order is late.\nAgent: I'm sorry, let me check."
    )

    assert parsed == [
        {"role": "customer", "text": "My order is late."},
        {"role": "agent", "text": "I'm sorry, let me check."},
    ]


def test_manual_and_replay_setup_validation():
    assert validation.validate_setup("Manual", PRODUCT, SCENARIO, []) == []
    assert validation.validate_setup("Manual", "", "", []) != []
    assert validation.validate_setup("Replay", PRODUCT, SCENARIO, []) != []
    assert validation.validate_setup("Replay", PRODUCT, SCENARIO, [{}] * 2) == []


def test_existing_orchestrator_workflow_still_completes():
    response = run_workflow(
        WorkflowRequest(session_id="sess-demo01", message="My order is late."),
        MockSessionManager(),
        MockAgent(),
    )

    assert response.status == "completed"
    assert response.result
    assert isinstance(response.result, dict)


def test_intent_agent_still_returns_agent_result():
    session = MockSessionManager().get_session("sess-demo01")
    result = IntentSentimentAgent().run(session, "My order has not arrived yet.")

    assert isinstance(result, AgentResult)
    assert result.result
    assert result.result["intent"] == "order_or_service_status"
