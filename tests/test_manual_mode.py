"""Manual Mode tests (Milestone 3).

These exercise the real Manual Mode path: validation -> conversation storage
-> the existing Intent & Sentiment Analysis Agent -> knowledge retrieval ->
coaching/escalation output.  Only the knowledge-base lookup is stubbed, and
only when the test is about how retrieved chunks flow into the console.
"""

from __future__ import annotations

import pytest

from backend.modes import coaching, manual

PRODUCT = "Acme Wireless Router X200"
SCENARIO = "Customer's order has not arrived after ten days."


def make_session(mode: str = "Manual", sid: str = "manual01") -> dict:
    return {
        "sid": sid,
        "config": {
            "mode": mode,
            "product": PRODUCT,
            "scenario": SCENARIO,
            "persona": "Calm",
            "max_turns": 5,
            "replay_script": [],
        },
        "messages": [],
        "analyses": [],
        "tone": [],
    }


# ---------------------------------------------------------------------------
# Session creation and validation
# ---------------------------------------------------------------------------


def test_manual_session_creation():
    session = make_session()
    assert manual.valid_session_id(session["sid"])
    assert session["config"]["mode"] == "Manual"

    turn = manual.submit_customer_message(session, "My order has not arrived yet.")

    assert turn.ok, turn.error
    assert turn.message == {
        "id": "msg-0001",
        "role": "customer",
        "text": "My order has not arrived yet.",
    }
    assert len(session["messages"]) == 1
    assert len(session["analyses"]) == 1


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_empty_message_is_rejected(text):
    session = make_session()

    turn = manual.submit_customer_message(session, text)

    assert not turn.ok
    assert "empty" in turn.error.lower()
    assert session["messages"] == []
    assert session["analyses"] == []


def test_long_message_is_rejected():
    session = make_session()
    too_long = "x" * (manual.MAX_MESSAGE_CHARS + 1)

    turn = manual.submit_customer_message(session, too_long)

    assert not turn.ok
    assert "too long" in turn.error.lower()
    assert session["messages"] == []


def test_message_at_the_limit_is_accepted():
    session = make_session()
    text = ("My order is delayed. " * 80)[: manual.MAX_MESSAGE_CHARS]

    turn = manual.submit_customer_message(session, text)

    assert turn.ok, turn.error
    assert manual.message_count(session, "customer") == 1


@pytest.mark.parametrize("sid", [None, "", "../escape", "bad id", 42])
def test_invalid_session_id_is_rejected(sid):
    session = make_session(sid=sid)

    turn = manual.submit_customer_message(session, "Hello, my order is late.")

    assert not turn.ok
    assert turn.invalid_session
    assert session["messages"] == []


def test_wrong_mode_is_rejected():
    session = make_session(mode="Replay")

    turn = manual.submit_customer_message(session, "My order is late.")

    assert not turn.ok
    assert "Manual Mode is not active" in turn.error
    assert session["messages"] == []


# ---------------------------------------------------------------------------
# Conversation turns
# ---------------------------------------------------------------------------


def test_multiple_messages_and_context_retention():
    session = make_session()

    first = manual.submit_customer_message(session, "My order has not arrived yet.")
    manual.submit_agent_reply(session, "I'm sorry about the delay. Let me check it.")
    second = manual.submit_customer_message(
        session, "I have already contacted support twice. This is ridiculous!"
    )

    assert first.ok and second.ok
    assert second.analysis["turn_number"] == 2
    assert second.analysis["conversation_context"]["customer_turns"] == 1
    assert second.analysis["conversation_context"]["has_context"] is True
    assert manual.message_count(session) == 3
    assert [m["role"] for m in session["messages"]] == [
        "customer",
        "agent",
        "customer",
    ]
    assert [m["id"] for m in session["messages"]] == [
        "msg-0001",
        "msg-0002",
        "msg-0003",
    ]


def test_agent_reply_is_scored_and_not_analysed_as_customer():
    session = make_session()

    turn = manual.submit_agent_reply(
        session, "I'm sorry for the delay. I've checked the tracking and I will update you today."
    )

    assert turn.ok
    assert turn.tone["score"] is not None
    assert 0 <= turn.tone["score"] <= 100
    assert turn.tone["notes"]
    assert session["analyses"] == []
    assert manual.message_count(session, "agent") == 1


def test_duplicate_customer_submission_is_prevented():
    session = make_session()
    manual.submit_customer_message(session, "My order has not arrived yet.")

    duplicate = manual.submit_customer_message(
        session, "  My order has not arrived yet.  "
    )

    assert not duplicate.ok
    assert duplicate.duplicate
    assert "already submitted" in duplicate.error
    assert manual.message_count(session) == 1
    assert len(session["analyses"]) == 1


def test_customer_may_repeat_after_agent_reply():
    session = make_session()
    manual.submit_customer_message(session, "My order has not arrived yet.")
    manual.submit_agent_reply(session, "I'm sorry, let me check the depot.")

    repeat = manual.submit_customer_message(
        session, "My order has not arrived yet."
    )

    assert repeat.ok, repeat.error
    assert manual.message_count(session, "customer") == 2


def test_duplicate_agent_reply_is_prevented():
    session = make_session()
    manual.submit_agent_reply(session, "Thanks for your patience.")

    duplicate = manual.submit_agent_reply(session, "thanks for your patience. ")

    assert not duplicate.ok
    assert duplicate.duplicate
    assert manual.message_count(session, "agent") == 1


def test_sessions_are_isolated():
    first = make_session(sid="sessionaa")
    second = make_session(sid="sessionbb")

    manual.submit_customer_message(first, "My order has not arrived yet.")
    manual.submit_customer_message(second, "My card was charged twice.")

    assert len(first["messages"]) == 1
    assert len(second["messages"]) == 1
    assert first["analyses"] is not second["analyses"]
    assert first["analyses"][0]["intent_label"] != second["analyses"][0]["intent_label"]
    assert second["analyses"][0]["conversation_context"]["customer_turns"] == 0


def test_multiple_concurrent_sessions_keep_their_own_context():
    first = make_session(sid="concurrent1")
    second = make_session(sid="concurrent2")

    for _ in range(2):
        manual.submit_customer_message(first, "My order has not arrived yet.")
        manual.submit_agent_reply(first, "Let me check that for you.")
        manual.submit_customer_message(second, "I cannot log in to my account.")
        manual.submit_agent_reply(second, "Let's reset your password.")

    assert manual.message_count(first, "customer") == 2
    assert manual.message_count(second, "customer") == 2
    assert first["analyses"][-1]["conversation_context"]["customer_turns"] == 1
    assert second["analyses"][-1]["conversation_context"]["customer_turns"] == 1
    assert second["analyses"][-1]["intent_label"] == "account_access"


# ---------------------------------------------------------------------------
# Agent output integration
# ---------------------------------------------------------------------------


def test_intent_detection():
    session = make_session()
    turn = manual.submit_customer_message(
        session, "My card was charged twice for the same order and I need a refund."
    )

    assert turn.analysis["intent_label"] == "billing_or_payment"
    assert turn.analysis["intent"] == "Billing or payment"
    assert turn.analysis["source"] == coaching.HANDOFF_SOURCE
    assert 0 <= turn.analysis["intent_confidence"] <= 1


def test_emotion_detection():
    session = make_session()
    turn = manual.submit_customer_message(
        session, "It's broken again. This is unacceptable, I'm furious!!"
    )

    emotions = turn.analysis["emotions"]
    assert "Anger" in emotions
    assert "Frustration" in emotions
    assert turn.analysis["emotion"] == "Frustration"


def test_frustration_classification():
    session = make_session()
    turn = manual.submit_customer_message(
        session, "It's broken again. This is unacceptable, I'm furious!!"
    )

    assert 0 <= turn.analysis["frustration"] <= 100
    assert turn.analysis["frustration_level"] in {
        "none",
        "low",
        "moderate",
        "high",
        "severe",
    }
    assert turn.analysis["frustration_level"] != "none"
    assert turn.analysis["frustration_score"] == pytest.approx(
        turn.analysis["frustration"] / 100, abs=0.01
    )


def test_sentiment_trajectory_is_recorded():
    session = make_session()
    manual.submit_customer_message(session, "Hi, my order is late but support was helpful.")
    manual.submit_agent_reply(session, "Thanks for your patience, I will chase it.")
    manual.submit_customer_message(session, "Okay it arrived today, great!")

    manual.submit_customer_message(
        session, "Now it's broken again. This is unacceptable, I'm furious!!"
    )
    latest = session["analyses"][-1]

    assert len(latest["sentiment_trajectory"]) >= 2
    assert latest["sentiment_trend"] in {"improving", "stable", "worsening"}
    assert latest["conversation_context"]["customer_turns"] == 2


def test_sentiment_worsening_is_detected():
    session = make_session()
    manual.submit_customer_message(session, "Hi, my order is late but the support was helpful.")
    manual.submit_agent_reply(session, "Thanks for your patience, I will chase it.")
    manual.submit_customer_message(session, "Okay it arrived today, great!")
    manual.submit_agent_reply(session, "Glad to hear it!")
    manual.submit_customer_message(
        session, "Now it's broken again. This is unacceptable, I'm furious!!"
    )
    manual.submit_agent_reply(session, "I'm sorry, let me help.")
    turn = manual.submit_customer_message(
        session, "Nothing works. I want a refund now."
    )

    assert turn.analysis["sentiment_trend"] == "worsening"


def test_knowledge_retrieval_flows_into_the_analysis(monkeypatch):
    chunks = [
        {
            "source": "shipping_and_delivery.pdf",
            "page": 2,
            "text": "Delayed orders are refunded after 10 business days.",
            "score": 1.42,
        }
    ]
    monkeypatch.setattr(coaching.rag_stub, "retrieve", lambda query, k=3: chunks)

    session = make_session()
    turn = manual.submit_customer_message(session, "My order has not arrived yet.")

    assert turn.analysis["chunks"] == chunks
    assert turn.analysis["knowledge_error"] is None
    assert "shipping_and_delivery.pdf" in turn.analysis["suggestion"]


def test_coaching_suggestions_are_produced():
    session = make_session()
    turn = manual.submit_customer_message(
        session, "I have already contacted support twice. This is ridiculous!"
    )

    analysis = turn.analysis
    assert analysis["coaching_focus"]
    assert analysis["coaching_guidance"]
    assert analysis["suggestion"].strip()
    assert analysis["strategy"].strip()


def test_escalation_integration():
    session = make_session()
    turn = manual.submit_customer_message(
        session,
        "This is the worst service ever! I'm furious and want to cancel my "
        "account. I will file a complaint and contact my lawyer!",
    )

    analysis = turn.analysis
    assert analysis["requires_human_review"] is True
    assert analysis["escalation_priority"] == "p2_high"
    assert analysis["signals"]
    assert analysis["risk_reason"]

    alert, message = coaching.escalation_alert(analysis)
    assert alert
    assert "HIGH ESCALATION RISK" in message


def test_escalation_alert_threshold():
    low = {"risk": 10, "requires_human_review": False}
    high = {"risk": 85, "requires_human_review": False, "escalation_priority_label": "P1 - Critical"}

    assert coaching.escalation_alert(low) == (False, "")
    alert, message = coaching.escalation_alert(high)
    assert alert
    assert "P1 - Critical" in message
    assert coaching.escalation_alert(None) == (False, "")


def test_agent_failure_falls_back_without_inventing_output(monkeypatch):
    def boom(message, history=None):
        raise RuntimeError("agent unavailable")

    monkeypatch.setattr(coaching, "analyze_message", boom)

    session = make_session()
    turn = manual.submit_customer_message(session, "My order has not arrived yet.")

    assert turn.ok
    assert turn.analysis["source"] == coaching.FALLBACK_SOURCE
    assert turn.analysis["error"] == "agent unavailable"
    assert turn.analysis["intent"]
    assert turn.analysis["suggestion"]


def test_analysis_error_is_reported_and_message_kept(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("analysis crashed")

    # Analyze itself raising (rather than the agent failing internally) must
    # be reported to the rep, not turned into invented coaching output.
    monkeypatch.setattr(manual.coaching, "analyze_customer_turn", boom)

    session = make_session()
    turn = manual.submit_customer_message(session, "My order has not arrived yet.")

    assert not turn.ok
    assert "Coaching analysis failed" in turn.error
    assert turn.message is not None
    assert manual.message_count(session) == 1
    assert session["analyses"] == []


def test_agent_reply_evaluation_failure_is_reported(monkeypatch):
    def boom(text):
        raise RuntimeError("tone service down")

    monkeypatch.setattr(coaching.fallback_pipeline, "evaluate_agent_reply", boom)

    tone = coaching.evaluate_agent_turn("I'm sorry, let me check.")

    assert tone["score"] is None
    assert tone["error"] == "tone service down"
    assert tone["notes"]
