"""
Automated tests for the orchestrator workflow.

Run from the project root:
    py -3 -m pytest tests/test_orchestrator.py -v

Tests focus exclusively on the orchestrator's behaviour.
No frontend, database, or RAG pipeline is required.
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.mock_components import MockAgent, MockSessionManager
from orchestrator.orchestrator import (
    run_workflow,
    run_multi_agent_workflow,
)
from orchestrator.schemas import WorkflowRequest, WorkflowResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def session_manager():
    """A fresh in-memory session manager with two pre-loaded sessions."""
    return MockSessionManager()


@pytest.fixture
def agent():
    """A normal mock agent that returns a valid AgentResult."""
    return MockAgent()


# ---------------------------------------------------------------------------
# Pydantic schema validation
# ---------------------------------------------------------------------------

def test_empty_session_id_raises_validation_error():
    """Pydantic rejects an empty session_id before the workflow runs."""
    with pytest.raises(ValidationError):
        WorkflowRequest(session_id="", message="Hello")


def test_whitespace_message_raises_validation_error():
    """Pydantic rejects a whitespace-only message before the workflow runs."""
    with pytest.raises(ValidationError):
        WorkflowRequest(session_id="sess-demo01", message="   ")


def test_valid_request_is_accepted():
    """A properly formed request is accepted without error."""
    request = WorkflowRequest(session_id="sess-demo01", message="Help me.")
    assert request.session_id == "sess-demo01"
    assert request.message == "Help me."


def test_response_model_structure():
    """WorkflowResponse stores all fields correctly."""
    response = WorkflowResponse(
        session_id="sess-demo01",
        status="completed",
        result={"answer": "ok"},
        error=None,
    )
    assert response.status == "completed"
    assert response.result == {"answer": "ok"}
    assert response.error is None


def test_response_rejects_invalid_status():
    """WorkflowResponse raises if status is not 'completed' or 'failed'."""
    with pytest.raises(ValidationError):
        WorkflowResponse(
            session_id="sess-demo01",
            status="unknown",
            result=None,
            error=None,
        )


# ---------------------------------------------------------------------------
# Workflow tests
# ---------------------------------------------------------------------------

def test_successful_workflow(session_manager, agent):
    """A valid request returns a completed response with an agent result."""
    request = WorkflowRequest(
        session_id="sess-demo01",
        message="Where is my order?",
    )
    response = run_workflow(request, session_manager, agent)

    assert response.status == "completed"
    assert response.session_id == "sess-demo01"
    assert isinstance(response.result, dict)
    assert response.result
    assert response.error is None


def test_unknown_session_returns_failure(session_manager, agent):
    """A session ID that does not exist returns a failed response."""
    request = WorkflowRequest(
        session_id="sess-does-not-exist",
        message="My package is late.",
    )
    response = run_workflow(request, session_manager, agent)

    assert response.status == "failed"
    assert response.session_id == "sess-does-not-exist"
    assert response.result is None
    assert response.error is not None


class BrokenSessionManager:
    """Simulates a session manager that raises on every call."""

    def get_session(self, session_id: str):
        raise ConnectionError("Simulated database connection failure.")


def test_session_manager_failure_is_handled(agent):
    """A session manager exception is caught and returns a safe failed response."""
    request = WorkflowRequest(session_id="sess-demo01", message="I need help.")
    response = run_workflow(request, BrokenSessionManager(), agent)

    assert response.status == "failed"
    assert response.result is None
    assert response.error is not None
    assert "traceback" not in response.error.lower()


def test_agent_failure_is_handled(session_manager):
    """An agent exception is caught and returns a safe failed response."""
    broken_agent = MockAgent(force_failure=True)
    request = WorkflowRequest(
        session_id="sess-demo01",
        message="My refund has not arrived.",
    )
    response = run_workflow(request, session_manager, broken_agent)

    assert response.status == "failed"
    assert response.result is None
    assert response.error is not None


def test_invalid_agent_response_is_rejected(session_manager):
    """An agent returning a plain dict instead of AgentResult fails the workflow."""
    bad_agent = MockAgent(return_bad_result=True)
    request = WorkflowRequest(
        session_id="sess-demo01",
        message="I want to cancel my order.",
    )
    response = run_workflow(request, session_manager, bad_agent)

    assert response.status == "failed"
    assert response.result is None
    assert response.error is not None


class UnpredictableAgent:
    """Raises an unexpected generic exception."""

    def run(self, session, message):
        raise Exception("Something completely unexpected happened.")


def test_unexpected_error_is_handled_safely(session_manager):
    """An unexpected exception is caught and does not expose a traceback."""
    request = WorkflowRequest(session_id="sess-demo01", message="Help please.")
    response = run_workflow(request, session_manager, UnpredictableAgent())

    assert response.status == "failed"
    assert response.result is None
    assert isinstance(response.error, str)
    assert "Traceback" not in response.error
    assert "Exception" not in response.error

# ---------------------------------------------------------------------------
# Milestone 2: Multi-agent workflow tests
# ---------------------------------------------------------------------------

class MockSentimentAgent:
    def analyze(self, session, message, **kwargs):
        return {
            "intent": "order_status",
            "sentiment": "frustrated",
            "analyzed_message": message,
        }


class MockKnowledgeAgent:
    def recommend(self, session, message, intent_sentiment, **kwargs):
        return {
            "recommendation": "Check shipment tracking.",
            "used_intent": intent_sentiment["intent"],
        }


class MockSimulatorAgent:
    def generate_message(self, session, message, **kwargs):
        return {
            "message": "My shipment is delayed. Where is my order?"
        }


class BrokenSentimentAgent:
    def analyze(self, session, message, **kwargs):
        raise RuntimeError("Simulated sentiment failure")


def test_multi_agent_manual_mode_success(session_manager):
    request = WorkflowRequest(
        session_id="sess-demo01",
        message="Where is my order?",
    )

    response = run_multi_agent_workflow(
        request=request,
        session_manager=session_manager,
        sentiment_agent=MockSentimentAgent(),
        knowledge_agent=MockKnowledgeAgent(),
    )

    assert response.status == "completed"
    assert response.error is None
    assert response.result["customer_message"] == "Where is my order?"
    assert response.result["intent_sentiment"]["intent"] == "order_status"
    assert response.result["knowledge_recommendation"]["used_intent"] == "order_status"
    assert response.result["simulator"]["used"] is False


def test_multi_agent_simulator_mode_success(session_manager):
    # MockSessionManager creates sess-demo01 and sess-demo02.
    # Find a session configured for Simulator mode.
    simulator_session = None

    for session_id in ("sess-demo01", "sess-sim01"):
        session = session_manager.get_session(session_id)

        if session is not None and str(
            getattr(session.mode, "value", session.mode)
        ).strip().lower() == "simulator":
            simulator_session = session
            break

    if simulator_session is None:
        pytest.skip(
            "MockSessionManager has no Simulator-mode session configured."
        )

    request = WorkflowRequest(
        session_id=simulator_session.session_id,
        message="Generate a customer message",
    )

    response = run_multi_agent_workflow(
        request=request,
        session_manager=session_manager,
        simulator_agent=MockSimulatorAgent(),
        sentiment_agent=MockSentimentAgent(),
        knowledge_agent=MockKnowledgeAgent(),
    )

    assert response.status == "completed"
    assert response.error is None
    assert response.result["simulator"]["used"] is True
    assert response.result["customer_message"] == (
        "My shipment is delayed. Where is my order?"
    )
    assert response.result["intent_sentiment"]["analyzed_message"] == (
        "My shipment is delayed. Where is my order?"
    )


def test_multi_agent_sentiment_failure_is_handled(session_manager):
    request = WorkflowRequest(
        session_id="sess-demo01",
        message="I need help with my order.",
    )

    response = run_multi_agent_workflow(
        request=request,
        session_manager=session_manager,
        sentiment_agent=BrokenSentimentAgent(),
        knowledge_agent=MockKnowledgeAgent(),
    )

    assert response.status == "failed"
    assert response.result is None
    assert response.error == (
        "Intent and sentiment analysis failed. Please try again."
    )
