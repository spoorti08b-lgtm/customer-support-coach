"""Tests for the extended intent, emotion, frustration, sentiment-tracking,
context-management, and agent hand-off behaviour.

Run from the project root:

    python -m pytest backend/tests/test_intent_emotion_context.py -v

The agent remains rule-based and CPU-local, so no model download, vector
store, network access, or frontend is required.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from backend.agents.agent_handoff import (
    AgentHandoff,
    build_handoff,
    escalation_priority,
    suggested_knowledge_query,
)
from backend.agents.conversation_context import ConversationContext
from backend.agents.intent_sentiment_agent import (
    IntentSentimentAgent,
    IntentSentimentResult,
    analyze_message,
)
from backend.agents.intent_sentiment_config import ScoringConfig
from backend.core.data_models import Session

FRUSTRATION_LEVELS = {"none", "low", "moderate", "high", "severe"}

CALM_MESSAGE = "Could you tell me when the store opens on weekdays?"
ANGRY_MESSAGE = (
    "I am absolutely furious, this is the worst service ever!!! "
    "You people are useless!!"
)
LEGAL_MESSAGE = "I will sue you and dispute the charge with my bank today."
CRITICAL_MESSAGE = "This is the third time, I will sue you and I am furious!!!"

HISTORY = [
    {"speaker": "customer", "content": "My payment failed.", "turn_number": 1},
    {"speaker": "agent", "content": "Let me check that for you.", "turn_number": 2},
    {
        "speaker": "customer",
        "content": "It failed again, this is frustrating.",
        "turn_number": 3,
    },
]


# ---------------------------------------------------------------------------
# Emotion detection
# ---------------------------------------------------------------------------


def test_happiness_emotion_detected():
    result = analyze_message("I am so happy and delighted, this is amazing!")
    assert "happiness" in result.emotion
    assert result.sentiment == "positive"


def test_satisfaction_and_happiness_are_distinct_labels():
    result = analyze_message("Thank you, the issue is resolved and I am thrilled!")
    assert {"satisfaction", "happiness"} <= set(result.emotion)


def test_required_emotion_labels_are_all_reachable():
    """The documented emotion set includes every label the task requires."""
    samples = {
        "anger": "I am furious and outraged.",
        "frustration": "I am fed up with this, third time now.",
        "confusion": "I am confused and I do not understand the invoice.",
        "happiness": "I am so happy and delighted with this!",
        "satisfaction": "Thanks, the issue is resolved and I am satisfied.",
    }
    for label, message in samples.items():
        assert label in analyze_message(message).emotion


# ---------------------------------------------------------------------------
# Frustration level
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, "none"),
        (0.19, "none"),
        (0.20, "low"),
        (0.39, "low"),
        (0.40, "moderate"),
        (0.59, "moderate"),
        (0.60, "high"),
        (0.79, "high"),
        (0.80, "severe"),
        (1.0, "severe"),
    ],
)
def test_frustration_level_bands(score, expected):
    assert IntentSentimentAgent()._frustration_level(score) == expected


def test_frustration_level_always_matches_reported_score():
    for message in (
        CALM_MESSAGE,
        ANGRY_MESSAGE,
        LEGAL_MESSAGE,
        "Thanks, that works perfectly now!",
        "ok",
    ):
        result = analyze_message(message)
        assert result.frustration_level in FRUSTRATION_LEVELS
        assert result.frustration_level == IntentSentimentAgent()._frustration_level(
            result.frustration_score
        )


def test_calm_message_has_no_frustration_band():
    result = analyze_message(CALM_MESSAGE)
    assert result.frustration_level == "none"


def test_angry_message_has_elevated_frustration_band():
    result = analyze_message(ANGRY_MESSAGE)
    assert result.frustration_level in {"moderate", "high", "severe"}
    assert result.frustration_score >= ScoringConfig().frustration_level_moderate


def test_frustration_bands_are_configurable():
    agent = IntentSentimentAgent(
        config=ScoringConfig(
            frustration_level_low=0.01,
            frustration_level_moderate=0.02,
            frustration_level_high=0.03,
            frustration_level_severe=0.04,
        )
    )
    result = agent.analyze(ANGRY_MESSAGE)
    assert result.frustration_level == "severe"


def test_non_increasing_frustration_bands_rejected():
    with pytest.raises(ValueError, match="strictly increasing"):
        ScoringConfig(frustration_level_high=0.1)
    with pytest.raises(ValueError, match="max_trajectory_points"):
        ScoringConfig(max_trajectory_points=0)


# ---------------------------------------------------------------------------
# Sentiment tracking across turns
# ---------------------------------------------------------------------------


def test_first_message_trajectory_has_one_current_point():
    result = analyze_message("My payment failed and I am angry.")
    assert len(result.sentiment_trajectory) == 1
    point = result.sentiment_trajectory[0]
    assert point.turn_number == 1
    assert point.sentiment == result.sentiment
    assert point.polarity < 0
    assert -1.0 <= point.polarity <= 1.0


def test_trajectory_tracks_customer_turns_only():
    result = analyze_message("Payment failed again, I am angry!", HISTORY)
    assert [p.turn_number for p in result.sentiment_trajectory] == [1, 3, 4]
    assert len(result.sentiment_trajectory) == 3
    assert result.sentiment_trajectory[-1].sentiment == result.sentiment
    assert result.sentiment_trajectory[-1].turn_number == result.turn_number


def test_trajectory_reflects_sentiment_change():
    result = analyze_message(
        "Thanks so much, it is fixed and works perfectly!",
        [
            {"speaker": "customer", "content": "This is terrible and useless!!"},
            {"speaker": "customer", "content": "I am furious, worst service ever!!!"},
        ],
    )
    polarities = [point.polarity for point in result.sentiment_trajectory]
    assert polarities[0] < 0 and polarities[-1] > 0
    assert result.sentiment_trend == "improving"


def test_trajectory_is_capped_to_recent_turns():
    history = [
        {"speaker": "customer", "content": f"Still broken, attempt {index}."}
        for index in range(1, 21)
    ]
    agent = IntentSentimentAgent(config=ScoringConfig(max_trajectory_points=3))
    result = agent.analyze("Nothing works at all!", history)
    assert len(result.sentiment_trajectory) == 3
    assert result.sentiment_trajectory[-1].turn_number == result.turn_number


def test_trajectory_points_are_serialisable():
    payload = json.dumps(analyze_message("Payment failed.", HISTORY).model_dump(mode="json"))
    assert "sentiment_trajectory" in payload


# ---------------------------------------------------------------------------
# Conversation context
# ---------------------------------------------------------------------------


def test_no_history_yields_empty_context():
    context = analyze_message("Hello, I have a question.").conversation_context
    assert isinstance(context, ConversationContext)
    assert context.has_context is False
    assert context.customer_turns == 0
    assert context.dominant_intent is None
    assert context.recurring_issue is False
    assert context.average_prior_frustration is None


def test_history_populates_intent_and_frustration_context():
    context = analyze_message(
        "Payment failed for the third time, I am confused and angry!", HISTORY
    ).conversation_context
    assert context.has_context is True
    assert context.customer_turns == 2
    assert context.window_start_turn == 1
    assert context.window_end_turn == 3
    assert len(context.prior_intents) == 2
    assert context.dominant_intent == "billing_or_payment"
    assert context.unresolved_turns >= 1
    assert context.recurring_issue is True
    assert 0.0 <= context.average_prior_frustration <= 1.0
    assert context.prior_emotion_counts


def test_agent_scenario_names_survive_training_session():
    """run(session, message) feeds session history into the context model."""
    session = Session(
        session_id="sess-demo01",
        mode="Manual",
        scenario=None,
        metadata={"conversation_history": HISTORY},
    )
    payload = IntentSentimentAgent().run(
        session=session, message="Payment failed again, I am angry!"
    ).result
    assert payload["conversation_context"]["has_context"] is True
    assert payload["conversation_context"]["dominant_intent"] == "billing_or_payment"
    assert payload["sentiment_trajectory"]
    assert payload["handoff"]["knowledge"]["intent"] == payload["intent"]


def test_context_and_handoff_never_echo_message_content():
    marker = "zebraconfidential42"
    result = analyze_message(
        f"My {marker} payment failed and I am confused about the charge!",
        ["My payment failed.".replace("payment", marker)],
    )
    serialised = json.dumps(result.model_dump(mode="json"))
    assert marker not in serialised


# ---------------------------------------------------------------------------
# Structured hand-off payloads
# ---------------------------------------------------------------------------


def test_handoff_contains_all_three_consumers():
    handoff = analyze_message("My payment failed.").handoff
    assert isinstance(handoff, AgentHandoff)
    assert handoff.knowledge.intent == "billing_or_payment"
    assert handoff.escalation.priority in {"p1_critical", "p2_high", "p3_medium", "p4_low"}
    assert handoff.coaching.focus_areas
    assert handoff.coaching.guidance.strip()


def test_handoff_is_json_serialisable():
    payload = analyze_message(ANGRY_MESSAGE).model_dump(mode="json")
    assert set(payload["handoff"]) == {"knowledge", "escalation", "coaching"}
    json.dumps(payload["handoff"])


def test_knowledge_handoff_carries_context_size_and_query():
    handoff = analyze_message("Payment failed again, I am angry!", HISTORY).handoff
    assert handoff.knowledge.customer_turns_of_context == 2
    assert handoff.knowledge.recurring_issue is True
    assert handoff.knowledge.turn_number == 4
    assert "billing or payment" in handoff.knowledge.suggested_query
    assert handoff.knowledge.sentiment == "negative"


def test_knowledge_query_is_derived_from_intent_label_only():
    assert suggested_knowledge_query("refund_or_cancellation") == (
        "refund or cancellation customer support policy"
    )
    assert len(suggested_knowledge_query("x" * 500)) <= 200


def test_escalation_priority_is_consistent_with_review_flag():
    for message in (
        CALM_MESSAGE,
        ANGRY_MESSAGE,
        LEGAL_MESSAGE,
        CRITICAL_MESSAGE,
        "Thanks, that works now!",
    ):
        result = analyze_message(message)
        priority = result.handoff.escalation.priority
        if result.requires_human_review:
            assert priority in {"p1_critical", "p2_high"}
        else:
            assert priority in {"p3_medium", "p4_low"}


def test_calm_message_routes_low_with_no_escalation_signals():
    handoff = analyze_message(CALM_MESSAGE).handoff
    assert handoff.escalation.priority == "p4_low"
    assert handoff.escalation.signals == ["no_escalation_signals"]
    assert "standard handling" in handoff.escalation.recommended_action


def test_legal_threat_routes_to_human():
    handoff = analyze_message(LEGAL_MESSAGE).handoff
    assert handoff.escalation.requires_human_review is True
    assert handoff.escalation.priority in {"p1_critical", "p2_high"}
    assert "legal_or_public_threat" in handoff.escalation.signals


def test_repeat_plus_legal_threat_is_critical():
    handoff = analyze_message(CRITICAL_MESSAGE).handoff
    assert handoff.escalation.priority == "p1_critical"
    assert "repeated_contact" in handoff.escalation.signals
    assert "Route to a senior support specialist" in (
        handoff.escalation.recommended_action
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"risk": 0.85, "frustration_level": "moderate", "requires_human_review": True}, "p1_critical"),
        ({"risk": 0.55, "frustration_level": "moderate", "requires_human_review": True}, "p2_high"),
        ({"risk": 0.30, "frustration_level": "high", "requires_human_review": False}, "p3_medium"),
        ({"risk": 0.30, "frustration_level": "low", "requires_human_review": False, "sentiment_trend": "worsening"}, "p3_medium"),
        ({"risk": 0.10, "frustration_level": "none", "requires_human_review": False}, "p4_low"),
    ],
)
def test_escalation_priority_mapping(kwargs, expected):
    assert escalation_priority(**kwargs) == expected


def test_coaching_handoff_targets_detected_emotion():
    handoff = analyze_message("I am confused and I do not understand this charge.").handoff
    assert handoff.coaching.dominant_emotion == "confusion"
    assert "clarify_and_confirm" in handoff.coaching.focus_areas


def test_worsening_trend_adds_recovery_focus():
    handoff = analyze_message(
        "Still waiting, nothing works and no one replies!!!", HISTORY
    ).handoff
    assert handoff.coaching.sentiment_trend == "worsening"
    assert "sentiment_recovery" in handoff.coaching.focus_areas


def test_recurring_issue_adds_context_continuity_focus():
    handoff = analyze_message("Payment failed again!", HISTORY).handoff
    assert "context_continuity" in handoff.coaching.focus_areas


def test_handoff_falls_back_to_neutral_for_unknown_emotion_labels():
    handoff = build_handoff(
        intent="other",
        intent_confidence=0.2,
        sentiment="neutral",
        emotions=["made_up_emotion"],
        turn_number=1,
        sentiment_trend="unknown",
        frustration_level="none",
        escalation_risk_score=0.0,
        requires_human_review=False,
        recurring_issue=False,
        customer_turns_of_context=0,
        signals=[],
    )
    assert handoff.coaching.dominant_emotion == "neutral"
    assert handoff.escalation.signals == ["no_escalation_signals"]


# ---------------------------------------------------------------------------
# Backward compatibility of the result model
# ---------------------------------------------------------------------------


def test_manually_built_result_keeps_new_fields_optional():
    result = IntentSentimentResult(
        sentiment="neutral",
        confidence=0.5,
        emotion=["neutral"],
        frustration_score=0.0,
        escalation_risk_score=0.0,
        requires_human_review=False,
        explanation="ok",
    )
    assert result.frustration_level == "none"
    assert result.turn_number == 1
    assert result.sentiment_trajectory == []
    assert result.conversation_context.has_context is False
    assert result.handoff is None


def test_result_rejects_unknown_frustration_level():
    with pytest.raises(ValidationError):
        IntentSentimentResult(
            sentiment="neutral",
            confidence=0.5,
            emotion=["neutral"],
            frustration_score=0.0,
            escalation_risk_score=0.0,
            requires_human_review=False,
            explanation="ok",
            frustration_level="extreme",
        )
