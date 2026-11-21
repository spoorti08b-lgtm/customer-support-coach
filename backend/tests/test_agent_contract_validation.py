import pytest
from pydantic import ValidationError

from backend.orchestrator.agent_contracts import (
    CustomerMessage,
    SimulatorInput,
    SentimentResult,
    AgentError,
)


def test_customer_message_rejects_blank_content():
    with pytest.raises(ValidationError):
        CustomerMessage(content="   ", turn_number=1)


def test_customer_message_rejects_invalid_turn_number():
    with pytest.raises(ValidationError):
        CustomerMessage(content="Hello", turn_number=0)


def test_simulator_input_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        SimulatorInput(session_id="session-1")


def test_sentiment_result_rejects_confidence_above_one():
    with pytest.raises(ValidationError):
        SentimentResult(sentiment="positive", confidence=1.2)


def test_sentiment_result_rejects_unknown_sentiment():
    with pytest.raises(ValidationError):
        SentimentResult(sentiment="angry", confidence=0.8)


def test_agent_error_rejects_blank_required_fields():
    with pytest.raises(ValidationError):
        AgentError(agent_name="", code="FAILED", message="Something went wrong")


def test_agent_error_defaults_to_non_retryable():
    error = AgentError(
        agent_name="sentiment",
        code="FAILED",
        message="Analysis failed",
    )
    assert error.retryable is False
    assert error.details == {}
