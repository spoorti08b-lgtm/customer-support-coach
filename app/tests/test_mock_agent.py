import pytest
from agents.mock_agent import MockAgent


def test_order_message():
    agent = MockAgent()
    assert "order ID" in agent.generate_response("Where is my order?")


def test_refund_message():
    agent = MockAgent()
    assert "refund" in agent.generate_response("I want a refund").lower()


def test_payment_message():
    agent = MockAgent()
    assert "transaction details" in agent.generate_response(
        "I was charged twice"
    )


def test_unknown_message():
    agent = MockAgent()
    assert "more details" in agent.generate_response(
        "I need help with my account"
    ).lower()


def test_empty_message():
    agent = MockAgent()
    with pytest.raises(ValueError):
        agent.generate_response("")


def test_invalid_input():
    agent = MockAgent()
    with pytest.raises(TypeError):
        agent.generate_response(None)