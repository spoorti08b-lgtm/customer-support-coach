import pytest
from pydantic import ValidationError

from backend.orchestrator.agent_contracts import (
    CustomerMessage,
    SimulatorInput,
    SimulatorOutput,
    SentimentResult,
    AgentError,
    TurnResult,
)


def test_customer_message_accepts_valid_content():
    message = CustomerMessage(content="My order is delayed.", turn_number=1)
    assert message.content == "My order is delayed."
    assert message.turn_number == 1


def test_customer_message_rejects_blank_content():
    with pytest.raises(ValidationError):
        CustomerMessage(content="   ", turn_number=1)


def test_simulator_input_accepts_valid_values():
    data = SimulatorInput(
        session_id="session-001",
        persona="A customer with a delayed order",
        turn_number=1,
        max_turns=5,
    )
    assert data.max_turns == 5


def test_simulator_input_rejects_invalid_turn_number():
    with pytest.raises(ValidationError):
        SimulatorInput(
            session_id="session-001",
            persona="Customer",
            turn_number=0,
            max_turns=5,
        )


def test_simulator_output_requires_customer_message():
    message = CustomerMessage(content="Where is my order?", turn_number=1)
    output = SimulatorOutput(message=message)
    assert output.message.content == "Where is my order?"


def test_sentiment_result_rejects_confidence_above_one():
    with pytest.raises(ValidationError):
        SentimentResult(sentiment="negative", confidence=1.5)


def test_sentiment_result_rejects_unknown_sentiment():
    with pytest.raises(ValidationError):
        SentimentResult(sentiment="angry", confidence=0.8)


def test_agent_error_accepts_valid_error():
    error = AgentError(
        agent_name="SentimentAgent",
        code="INVALID_INPUT",
        message="Customer message is missing.",
    )
    assert error.retryable is False


def test_turn_result_accepts_valid_result():
    message = CustomerMessage(content="My order is late.", turn_number=1)
    result = TurnResult(
        session_id="session-001",
        turn_number=1,
        customer_message=message,
        status="completed",
    )
    assert result.status == "completed"


def test_turn_result_rejects_invalid_status():
    message = CustomerMessage(content="Hello", turn_number=1)
    with pytest.raises(ValidationError):
        TurnResult(
            session_id="session-001",
            turn_number=1,
            customer_message=message,
            status="unknown",
        )


def test_simulator_input_requires_session_id():
    with pytest.raises(ValidationError):
        SimulatorInput(
            persona="Customer",
            turn_number=1,
            max_turns=5,
        )


def test_simulator_input_rejects_zero_max_turns():
    with pytest.raises(ValidationError):
        SimulatorInput(
            session_id="session-001",
            persona="Customer",
            turn_number=1,
            max_turns=0,
        )


def test_agent_error_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        AgentError(agent_name="SentimentAgent")


def test_turn_result_rejects_invalid_status():
    message = CustomerMessage(content="Hello", turn_number=1)

    with pytest.raises(ValidationError):
        TurnResult(
            session_id="session-001",
            turn_number=1,
            customer_message=message,
            status="unknown",
        )


def test_customer_message_rejects_extra_fields():
    with pytest.raises(ValidationError):
        CustomerMessage(
            content="Hello",
            turn_number=1,
            unexpected_field="not allowed",
        )
