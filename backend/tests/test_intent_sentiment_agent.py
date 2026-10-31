"""Automated tests for the Intent and Sentiment Analysis Agent.

Run from the project root:

    python -m pytest backend/tests/test_intent_sentiment_agent.py -v

No frontend, database, vector store, network access, or model download
is required — the agent is rule-based and fully CPU-local.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from backend.agents.intent_sentiment_agent import (
    AGENT_TYPE,
    IntentSentimentAgent,
    IntentSentimentResult,
    analyze_message,
)
from backend.agents.intent_sentiment_config import (
    DEFAULT_INTENT_KEYWORDS,
    ScoringConfig,
)
from backend.core.data_models import AgentResult, Session
from backend.orchestrator.agent_contracts import CustomerMessage, SentimentResult

DEFAULT_INTENTS = set(DEFAULT_INTENT_KEYWORDS)
EMOTION_LABELS = {
    "frustration",
    "anger",
    "confusion",
    "disappointment",
    "satisfaction",
    "urgency",
    "neutral",
}
SENTIMENT_LABELS = {"positive", "neutral", "negative", "mixed"}
TREND_LABELS = {"improving", "stable", "worsening", "unknown"}

# ---------------------------------------------------------------------------
# Sample messages used across the suite
# ---------------------------------------------------------------------------

POSITIVE_MESSAGE = (
    "Thank you so much! The issue is fixed, everything works and I am happy."
)
NEUTRAL_MESSAGE = "Your package contains three items and the invoice is enclosed."
NEGATIVE_MESSAGE = "The product is broken and the delivery was late. This is terrible."
MIXED_MESSAGE = "The product quality is great, but the support was terrible."
ANGRY_MESSAGE = (
    "I am absolutely furious, this is the worst service ever!!! "
    "You people are useless!!"
)
CALM_MESSAGE = "Could you tell me when the store opens on weekdays?"
REPEAT_MESSAGE = "Third time contacting you and still no response!!!"
MANAGER_MESSAGE = "This is unacceptable, I want a manager right now!!"
LEGAL_MESSAGE = "I will sue you and dispute the charge with my bank today."

INTENT_SAMPLES = {
    "billing_or_payment": "I was charged twice for the same payment.",
    "technical_issue": "The app crashes with an error every time I open it.",
    "account_access": "I am locked out and cannot reset my password.",
    "refund_or_cancellation": "I want a refund and to cancel my subscription.",
    "order_or_service_status": "Where is my order? The tracking has not updated.",
    "product_information": "What are the specs and is this model compatible?",
    "complaint": "I would like to file a formal complaint about your unacceptable service.",
    "general_inquiry": "Hello, could you tell me how do I contact support?",
    "other": "ok",
}

BROAD_CORPUS = [
    POSITIVE_MESSAGE,
    NEUTRAL_MESSAGE,
    NEGATIVE_MESSAGE,
    MIXED_MESSAGE,
    ANGRY_MESSAGE,
    CALM_MESSAGE,
    REPEAT_MESSAGE,
    MANAGER_MESSAGE,
    LEGAL_MESSAGE,
    *INTENT_SAMPLES.values(),
    "!!! ??? ...",
    "emoji only test \U0001F600\U0001F621",
]


def assert_valid_result(result: IntentSentimentResult) -> None:
    """Shared invariant checks for every analysis result."""
    assert isinstance(result, IntentSentimentResult)
    assert isinstance(result, SentimentResult)

    assert result.sentiment in SENTIMENT_LABELS
    assert 0.0 <= result.confidence <= 1.0
    assert result.intent is not None and result.intent.strip()
    assert result.intent_confidence is not None
    assert 0.0 <= result.intent_confidence <= 1.0

    assert result.emotion
    assert set(result.emotion) <= EMOTION_LABELS
    assert 0.0 <= result.frustration_score <= 1.0
    assert 0.0 <= result.escalation_risk_score <= 1.0
    assert isinstance(result.requires_human_review, bool)
    assert result.explanation.strip()
    assert result.sentiment_trend in TREND_LABELS


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------


def test_output_schema_matches_documented_contract():
    """The result exposes every field of the suggested output contract."""
    result = analyze_message(INTENT_SAMPLES["billing_or_payment"])
    expected_fields = {
        "sentiment",
        "confidence",
        "intent",
        "intent_confidence",
        "emotion",
        "frustration_score",
        "escalation_risk_score",
        "requires_human_review",
        "explanation",
        "sentiment_trend",
    }
    assert set(result.model_dump()) == expected_fields


def test_result_is_a_sentiment_result():
    """The typed output extends the shared Milestone 2 SentimentResult."""
    result = analyze_message("Thanks for the help!")
    assert isinstance(result, SentimentResult)


def test_result_is_json_serialisable():
    """model_dump(mode='json') round-trips through the stdlib json module."""
    result = analyze_message(NEGATIVE_MESSAGE)
    payload = json.loads(json.dumps(result.model_dump(mode="json")))
    assert payload["sentiment"] in SENTIMENT_LABELS
    assert isinstance(payload["emotion"], list)


def test_result_rejects_out_of_range_scores():
    with pytest.raises(ValidationError):
        IntentSentimentResult(
            sentiment="negative",
            confidence=0.5,
            emotion=["frustration"],
            frustration_score=1.5,
            escalation_risk_score=0.2,
            requires_human_review=False,
            explanation="ok",
        )


def test_result_rejects_unknown_emotion_label():
    with pytest.raises(ValidationError):
        IntentSentimentResult(
            sentiment="negative",
            confidence=0.5,
            emotion=["rage"],
            frustration_score=0.2,
            escalation_risk_score=0.2,
            requires_human_review=False,
            explanation="ok",
        )


def test_result_rejects_extra_fields():
    with pytest.raises(ValidationError):
        IntentSentimentResult(
            sentiment="neutral",
            confidence=0.5,
            emotion=["neutral"],
            frustration_score=0.0,
            escalation_risk_score=0.0,
            requires_human_review=False,
            explanation="ok",
            made_up_field="nope",
        )


def test_to_agent_result_uses_shared_agent_result():
    result = analyze_message("Where is my order?")
    agent_result = result.to_agent_result(session_id="sess-demo01")
    assert isinstance(agent_result, AgentResult)
    assert agent_result.session_id == "sess-demo01"
    assert agent_result.agent_type == AGENT_TYPE
    assert agent_result.result["intent"] == result.intent


def test_to_agent_result_sanitises_invalid_session_id():
    result = analyze_message("Where is my order?")
    agent_result = result.to_agent_result(session_id="not a valid id!!")
    assert agent_result.session_id == "sess-default"


# ---------------------------------------------------------------------------
# Sentiment analysis
# ---------------------------------------------------------------------------


def test_positive_message_sentiment():
    result = analyze_message(POSITIVE_MESSAGE)
    assert result.sentiment == "positive"
    assert result.confidence > 0.4
    assert "satisfaction" in result.emotion


def test_neutral_message_sentiment():
    result = analyze_message(NEUTRAL_MESSAGE)
    assert result.sentiment == "neutral"


def test_negative_message_sentiment():
    result = analyze_message(NEGATIVE_MESSAGE)
    assert result.sentiment == "negative"
    assert result.confidence > 0.4


def test_balanced_message_is_mixed():
    result = analyze_message(MIXED_MESSAGE)
    assert result.sentiment == "mixed"


def test_negation_flips_polarity():
    """'not happy' must not be read as positive."""
    result = analyze_message("I am not happy with this service.")
    assert result.sentiment != "positive"


def test_sentiment_confidence_is_bounded_and_nonzero_for_clear_cues():
    result = analyze_message("Thanks, that was brilliant and perfect.")
    assert 0.0 < result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Intent classification — one sample per category
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("expected", sorted(DEFAULT_INTENTS))
def test_each_default_intent_label_is_reachable(expected):
    message = INTENT_SAMPLES[expected]
    result = analyze_message(message)
    assert_valid_result(result)
    assert result.intent == expected


def test_intent_confidence_low_for_ambiguous_message():
    """A message with competing intents scores below a clear one."""
    clear = analyze_message("I want a refund.")
    ambiguous = analyze_message("Please refund the broken app subscription.")
    assert ambiguous.intent_confidence < clear.intent_confidence


def test_fallback_labels_have_low_confidence():
    result = analyze_message("ok")
    assert result.intent in {"other", "general_inquiry"}
    assert result.intent_confidence <= 0.30


def test_configurable_intent_labels():
    agent = IntentSentimentAgent(
        intent_keywords={
            "payments_trouble": ("payment", "billing"),
            "greetings": ("hello",),
        }
    )
    result = agent.analyze("The payment failed")
    assert result.intent == "payments_trouble"
    assert set(analyze_message("hello").model_dump()) == set(
        agent.analyze("hello").model_dump()
    )


def test_invalid_intent_keyword_configuration_rejected():
    with pytest.raises(ValueError, match="at least one intent label"):
        IntentSentimentAgent(intent_keywords={})
    with pytest.raises(ValueError, match="non-empty sequence"):
        IntentSentimentAgent(intent_keywords={"x": ()})
    with pytest.raises(ValueError, match="non-empty string"):
        IntentSentimentAgent(intent_keywords={"  ": ("kw",)})
    with pytest.raises(ValueError, match="empty keyword entry"):
        IntentSentimentAgent(intent_keywords={"x": ("  ",)})


# ---------------------------------------------------------------------------
# Emotion detection
# ---------------------------------------------------------------------------


def test_multiple_emotions_detected():
    result = analyze_message(
        "I am confused and frustrated because nobody explained this urgent issue."
    )
    assert "confusion" in result.emotion
    assert "frustration" in result.emotion


def test_neutral_emotion_when_nothing_detected():
    result = analyze_message(NEUTRAL_MESSAGE)
    assert result.emotion == ["neutral"]


def test_urgency_emotion():
    result = analyze_message("This is urgent, please respond immediately.")
    assert "urgency" in result.emotion


def test_anger_emotion():
    result = analyze_message(ANGRY_MESSAGE)
    assert "anger" in result.emotion


# ---------------------------------------------------------------------------
# Frustration and escalation risk
# ---------------------------------------------------------------------------


def test_scores_are_always_in_unit_range():
    for message in BROAD_CORPUS:
        result = analyze_message(message)
        assert_valid_result(result)


def test_angry_message_more_frustrated_than_calm_message():
    angry = analyze_message(ANGRY_MESSAGE)
    calm = analyze_message(CALM_MESSAGE)
    assert angry.frustration_score > calm.frustration_score
    assert angry.frustration_score >= 0.4
    assert calm.frustration_score <= 0.2


def test_negative_sentiment_alone_never_requires_human_review():
    """Strongly negative wording without escalation triggers stays below review."""
    for message in (
        ANGRY_MESSAGE,
        "This is terrible, awful, horrible and useless garbage.",
        "I hate this bad poor awful product, worst thing ever!!!",
    ):
        result = analyze_message(message)
        assert result.sentiment == "negative"
        assert result.requires_human_review is False
        assert result.escalation_risk_score < 0.5


def test_review_flag_consistent_with_configured_threshold():
    agent = IntentSentimentAgent()
    for message in BROAD_CORPUS:
        result = agent.analyze(message)
        expected = (
            result.escalation_risk_score >= agent.config.human_review_risk_threshold
        )
        assert result.requires_human_review is expected


def test_review_impossible_from_frustration_and_urgency_alone():
    """Structural guarantee: trigger or repeat evidence is always required."""
    config = ScoringConfig()
    assert (
        config.risk_weight_frustration + config.risk_weight_urgency
        < config.human_review_risk_threshold
    )


def test_explicit_manager_request_raises_risk():
    plain = analyze_message("I have a billing problem.")
    manager = analyze_message(MANAGER_MESSAGE)
    assert manager.escalation_risk_score > plain.escalation_risk_score
    assert manager.requires_human_review is True


def test_legal_threat_requires_human_review():
    result = analyze_message(LEGAL_MESSAGE)
    assert result.requires_human_review is True
    assert result.escalation_risk_score >= 0.5


def test_repeated_unresolved_contact_requires_human_review():
    result = analyze_message(REPEAT_MESSAGE)
    assert result.requires_human_review is True
    assert result.escalation_risk_score >= 0.5
    assert "repeatedly" in result.explanation


def test_recurring_history_increases_risk():
    message = "The payment is still failing after your last fix."
    without = analyze_message(message)
    with_history = analyze_message(
        message,
        [
            {"speaker": "customer", "content": "My payment failed."},
            {"speaker": "customer", "content": "Payment failed again."},
        ],
    )
    assert with_history.escalation_risk_score > without.escalation_risk_score
    assert "repeatedly" in with_history.explanation


def test_explanation_never_echoes_message_content():
    marker = "zebraconfidential42"
    result = analyze_message(
        f"My {marker} payment failed and I am angry!!!"
    )
    assert marker not in result.explanation
    assert result.explanation.strip().endswith(".")


def test_calm_message_has_no_escalation_signals():
    result = analyze_message(CALM_MESSAGE)
    assert result.escalation_risk_score < 0.2
    assert result.requires_human_review is False
    assert "No strong escalation signals" in result.explanation


# ---------------------------------------------------------------------------
# Conversation history and sentiment trends
# ---------------------------------------------------------------------------


def test_no_history_means_unknown_trend():
    assert analyze_message(NEGATIVE_MESSAGE).sentiment_trend == "unknown"


def test_single_prior_message_means_unknown_trend():
    result = analyze_message(
        "This is terrible.",
        [{"speaker": "customer", "content": "Thanks, great job!"}],
    )
    assert result.sentiment_trend == "unknown"


def test_deteriorating_history_reports_worsening_trend():
    result = analyze_message(
        "Still waiting, nothing works and no one replies!!!",
        [
            {"speaker": "customer", "content": "Thanks for the quick help!"},
            {"speaker": "customer", "content": "Great, all good now."},
        ],
    )
    assert result.sentiment_trend == "worsening"


def test_improving_history_reports_improving_trend():
    result = analyze_message(
        "Thanks so much, it is fixed and works perfectly!",
        [
            {"speaker": "customer", "content": "This is terrible and useless!!"},
            {"speaker": "customer", "content": "I am furious, worst service ever!!!"},
        ],
    )
    assert result.sentiment_trend == "improving"


def test_flat_history_reports_stable_trend():
    result = analyze_message(
        "Still nothing, this is awful.",
        [
            {"speaker": "customer", "content": "This is terrible and useless!!"},
            {"speaker": "customer", "content": "I am furious, worst service ever!!!"},
        ],
    )
    assert result.sentiment_trend == "stable"


def test_agent_turns_are_ignored_for_trend():
    """Only prior customer messages count as history."""
    result = analyze_message(
        "This is terrible.",
        [
            {"speaker": "agent", "content": "Thanks, great job!"},
            {"speaker": "agent", "content": "All good now."},
        ],
    )
    assert result.sentiment_trend == "unknown"


def test_history_accepts_dicts_dataclasses_and_models():
    from backend.core.data_models import ConversationMessage, Speaker

    dataclass_item = ConversationMessage(
        session_id="sess-demo01",
        speaker=Speaker.CUSTOMER,
        content="My payment failed.",
        turn_number=1,
    )
    model_item = {"speaker": "customer", "content": "Still not fixed."}

    result = analyze_message(
        "Now nothing works at all!",
        [dataclass_item, model_item],
    )
    assert_valid_result(result)
    assert result.sentiment_trend in TREND_LABELS


def test_malformed_history_entries_are_skipped():
    result = analyze_message(
        "This is bad.",
        [
            None,
            {},
            {"speaker": "customer", "content": "   "},
            {"speaker": "unknown-role", "content": "hello"},
            {"speaker": "customer", "content": "The app crashed."},
        ],
    )
    assert_valid_result(result)


def test_history_as_string_raises_type_error():
    with pytest.raises(TypeError, match="sequence of messages"):
        analyze_message("Hello", "Customer: hi")


# ---------------------------------------------------------------------------
# Empty, invalid, and unusual inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_message", ["", "   ", "\n\t  ", None, 42, ["list"]])
def test_invalid_messages_raise_validation_error(bad_message):
    with pytest.raises(ValidationError):
        analyze_message(bad_message)


def test_punctuation_only_message_is_handled():
    result = analyze_message("!!! ??? ...")
    assert_valid_result(result)


def test_unicode_and_emoji_message_is_handled():
    result = analyze_message("Ño ño ño — ¿dónde está mi pedido? 🚚😡")
    assert_valid_result(result)


def test_unusually_long_message_is_truncated_and_fast():
    long_message = "This is broken and not working!! " * 3000
    result = analyze_message(long_message)
    assert_valid_result(result)
    # Truncation keeps scoring bounded: results must match the first window.
    truncated = analyze_message(long_message[:4000])
    assert result.intent == truncated.intent
    assert result.frustration_score == truncated.frustration_score


def test_accepts_prebuilt_customer_message():
    customer = CustomerMessage(content="I need a refund.", turn_number=3)
    result = analyze_message(customer)
    assert result.intent == "refund_or_cancellation"


def test_missing_optional_context_is_safe():
    assert analyze_message("Hello").sentiment_trend == "unknown"


# ---------------------------------------------------------------------------
# Determinism / repeatability
# ---------------------------------------------------------------------------


def test_rule_based_output_is_repeatable():
    for message in BROAD_CORPUS:
        first = analyze_message(message)
        second = analyze_message(message)
        assert first.model_dump() == second.model_dump()


def test_default_agent_and_shared_instance_agree():
    agent = IntentSentimentAgent()
    message = ANGRY_MESSAGE
    assert agent.analyze(message).model_dump() == analyze_message(message).model_dump()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_custom_scoring_config_is_honoured():
    always_review = IntentSentimentAgent(
        config=ScoringConfig(human_review_risk_threshold=0.0)
    )
    result = always_review.analyze(CALM_MESSAGE)
    assert result.requires_human_review is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"human_review_risk_threshold": 2.0},
        {"max_analysis_chars": 0},
        {"min_history_for_trend": 0},
        {"history_window": -1},
        {"negative_saturation_half": 0.0},
    ],
)
def test_invalid_scoring_config_rejected(kwargs):
    with pytest.raises(ValueError):
        ScoringConfig(**kwargs)


# ---------------------------------------------------------------------------
# Orchestrator integration: run(session, message) -> AgentResult
# ---------------------------------------------------------------------------


@pytest.fixture
def session() -> Session:
    return Session(session_id="sess-demo01", mode="Manual", scenario=None)


def test_run_returns_agent_result_with_json_payload(session):
    agent = IntentSentimentAgent()
    agent_result = agent.run(
        session=session, message="My payment failed, please help."
    )
    assert isinstance(agent_result, AgentResult)
    assert agent_result.agent_type == AGENT_TYPE
    assert agent_result.session_id == "sess-demo01"
    payload = agent_result.result
    json.dumps(payload)  # must not raise
    assert payload["intent"] == "billing_or_payment"
    assert set(payload) >= {
        "sentiment",
        "intent",
        "frustration_score",
        "escalation_risk_score",
        "requires_human_review",
        "explanation",
        "sentiment_trend",
    }


def test_run_never_raises_on_invalid_message(session):
    agent = IntentSentimentAgent()
    agent_result = agent.run(session=session, message="   ")
    payload = agent_result.result
    assert payload["status"] == "failed"
    error = payload["errors"][0]
    assert error["code"] == "INVALID_INPUT"
    assert error["retryable"] is False
    # The raw input must not be echoed back in diagnostics.
    assert "input" not in error["details"]


def test_run_handles_missing_session():
    agent = IntentSentimentAgent()
    agent_result = agent.run(session=None, message="Hello")
    assert agent_result.session_id == "sess-default"
    assert agent_result.result["intent"] in DEFAULT_INTENTS


def test_run_reads_history_from_session_metadata():
    session = Session(
        session_id="sess-demo01",
        mode="Manual",
        scenario=None,
        metadata={
            "conversation_history": [
                {"speaker": "customer", "content": "Payment failed."},
                {"speaker": "customer", "content": "Payment failed again."},
            ]
        },
    )
    agent = IntentSentimentAgent()
    result = agent.analyze(
        "Payment still fails!",
        conversation_history=agent._history_from_session(session),
    )
    assert result.sentiment_trend != "unknown"


def test_orchestrator_workflow_with_this_agent():
    """End-to-end: run_workflow drives this agent through the backend orchestrator."""
    from backend.orchestrator.mock_components import MockSessionManager
    from backend.orchestrator.orchestrator import run_workflow
    from backend.orchestrator.schemas import WorkflowRequest

    response = run_workflow(
        WorkflowRequest(session_id="sess-demo01", message=LEGAL_MESSAGE),
        MockSessionManager(),
        IntentSentimentAgent(),
    )
    assert response.status == "completed"
    assert response.error is None
    assert response.result["requires_human_review"] is True
