"""Focused tests for the Knowledge Recommendation Agent input/output contract.

Covers:
  - Input validation (valid inputs, whitespace rejection, limit bounds, ID validation)
  - History coercion (dicts, ConversationMessage, Speaker enum)
  - RetrievedPassage metadata and ranking
  - Distinct outcomes (success, no_match, error) and consistency validation
  - Pydantic v2 serialization (.model_dump(), .model_dump_json(), round-trip)
  - Conversion to core AgentResult for orchestrator compatibility
  - Agent execution and fallback behavior
"""

from __future__ import annotations

import json
from unittest.mock import patch
import pytest
from pydantic import ValidationError

from backend.core.data_models import AgentResult, ConversationMessage, Session, Speaker
from backend.orchestrator.knowledge_schemas import (
    ConversationHistoryItem,
    KnowledgeExecutionStatus,
    KnowledgeRecommendationRequest,
    KnowledgeRecommendationResponse,
    RetrievedPassage,
)
from backend.services.knowledge_agent import KnowledgeRecommendationAgent


# ---------------------------------------------------------------------------
# 1. Request Schema Validation
# ---------------------------------------------------------------------------

def test_request_minimal_valid():
    """A request with only the required message is valid and sets default limit to 3."""
    req = KnowledgeRecommendationRequest(message="What is the refund window?")
    assert req.message == "What is the refund window?"
    assert req.intent is None
    assert req.history == []
    assert req.session_id is None
    assert req.kb_identifier == "support_kb"
    assert req.limit == 3


def test_request_full_valid():
    """A request with all optional fields is accepted with normalized values."""
    req = KnowledgeRecommendationRequest(
        message="Where is my parcel?",
        intent="Delivery / order",
        session_id="sess-abc123",
        kb_identifier="custom_kb",
        limit=5,
        history=[
            {"speaker": "customer", "content": "I ordered 3 days ago.", "turn_number": 1},
            {"speaker": "agent", "content": "Let me look up your order.", "turn_number": 2},
        ],
    )
    assert req.intent == "Delivery / order"
    assert req.session_id == "sess-abc123"
    assert req.kb_identifier == "custom_kb"
    assert req.limit == 5
    assert len(req.history) == 2
    assert req.history[0].speaker == "customer"
    assert req.history[1].speaker == "agent"


def test_request_rejects_empty_or_whitespace_message():
    """Empty or whitespace-only messages are strictly rejected."""
    with pytest.raises(ValidationError) as exc1:
        KnowledgeRecommendationRequest(message="")
    assert "Customer message must not be empty" in str(exc1.value)

    with pytest.raises(ValidationError) as exc2:
        KnowledgeRecommendationRequest(message="   \n\t  ")
    assert "Customer message must not be empty" in str(exc2.value)


@pytest.mark.parametrize("invalid_limit", [0, -1, 21, 100])
def test_request_rejects_out_of_bound_limits(invalid_limit):
    """Limits outside the range [1, 20] are rejected."""
    with pytest.raises(ValidationError):
        KnowledgeRecommendationRequest(
            message="Check return status",
            limit=invalid_limit,
        )


def test_request_rejects_invalid_session_id():
    """Session IDs violating character whitelist or length are rejected."""
    with pytest.raises(ValidationError):
        KnowledgeRecommendationRequest(
            message="Valid question",
            session_id="invalid/session/id!@#",
        )


# ---------------------------------------------------------------------------
# 2. History Item Coercion & Speaker Validation
# ---------------------------------------------------------------------------

def test_history_coercion_from_core_conversation_message():
    """Core ConversationMessage dataclass instances are cleanly coerced into history items."""
    msg = ConversationMessage(
        session_id="sess-100",
        speaker=Speaker.CUSTOMER,
        content="I need a replacement battery.",
        turn_number=1,
    )
    req = KnowledgeRecommendationRequest(
        message="Is this covered under warranty?",
        history=[msg],
    )
    assert len(req.history) == 1
    assert req.history[0].speaker == "customer"
    assert req.history[0].content == "I need a replacement battery."
    assert req.history[0].turn_number == 1


def test_history_coercion_from_frontend_role_dict():
    """Legacy/frontend dicts with 'role' and 'text' keys are normalized."""
    req = KnowledgeRecommendationRequest(
        message="What are your hours?",
        history=[
            {"role": "customer", "text": "Hello there"},
            {"role": "agent", "text": "Hi! How can I help?"},
        ],
    )
    assert len(req.history) == 2
    assert req.history[0].speaker == "customer"
    assert req.history[0].content == "Hello there"
    assert req.history[1].speaker == "agent"
    assert req.history[1].content == "Hi! How can I help?"


def test_history_rejects_invalid_speaker():
    """Speakers other than customer, agent, or system raise a validation error."""
    with pytest.raises(ValidationError):
        ConversationHistoryItem(speaker="supervisor", content="Escalating now.")


# ---------------------------------------------------------------------------
# 3. RetrievedPassage Validation
# ---------------------------------------------------------------------------

def test_retrieved_passage_auto_syncs_doc_name():
    """If doc_name is omitted, it automatically syncs from source."""
    passage = RetrievedPassage(
        text="Returns are accepted within 30 days.",
        source="returns_and_refunds.pdf",
        rank=1,
        score=0.92,
        page=1,
    )
    assert passage.doc_name == "returns_and_refunds.pdf"
    assert passage.rank == 1
    assert passage.score == 0.92


def test_retrieved_passage_rejects_rank_less_than_one():
    """Rank must be a positive 1-indexed integer."""
    with pytest.raises(ValidationError):
        RetrievedPassage(
            text="Valid passage",
            source="shipping.pdf",
            rank=0,
        )


# ---------------------------------------------------------------------------
# 4. Distinct Outcome Representation (Success, No-Match, Error)
# ---------------------------------------------------------------------------

def test_outcome_success():
    """Success outcome requires passages, no_match=False, and error=None."""
    passage = RetrievedPassage(
        text="Standard delivery takes 3 to 5 business days.",
        source="shipping_and_delivery.pdf",
        rank=1,
        score=0.88,
        page=1,
    )
    resp = KnowledgeRecommendationResponse.create_success(
        query="shipping timeframe",
        passages=[passage],
        session_id="sess-001",
    )
    assert resp.status == KnowledgeExecutionStatus.SUCCESS
    assert resp.no_match is False
    assert resp.error is None
    assert len(resp.passages) == 1
    assert resp.query == "shipping timeframe"


def test_outcome_no_match():
    """No-match outcome requires empty passages, no_match=True, and error=None."""
    resp = KnowledgeRecommendationResponse.create_no_match(
        query="space shuttle repair guidelines",
        session_id="sess-002",
    )
    assert resp.status == KnowledgeExecutionStatus.NO_MATCH
    assert resp.no_match is True
    assert resp.error is None
    assert resp.passages == []


def test_outcome_error():
    """Error outcome requires a non-empty error message and empty passages."""
    resp = KnowledgeRecommendationResponse.create_error(
        error_message="ChromaDB connection timed out.",
        query="damaged package claim",
        session_id="sess-003",
    )
    assert resp.status == KnowledgeExecutionStatus.ERROR
    assert resp.no_match is False
    assert resp.error == "ChromaDB connection timed out."
    assert resp.passages == []


def test_response_rejects_inconsistent_outcomes():
    """Enforces outcome consistency across status, passages, no_match, and error."""
    # Success cannot have empty passages
    with pytest.raises(ValidationError):
        KnowledgeRecommendationResponse(
            status=KnowledgeExecutionStatus.SUCCESS,
            passages=[],
            no_match=False,
        )

    # Success cannot have no_match=True
    passage = RetrievedPassage(text="Valid", source="faq.pdf", rank=1)
    with pytest.raises(ValidationError):
        KnowledgeRecommendationResponse(
            status=KnowledgeExecutionStatus.SUCCESS,
            passages=[passage],
            no_match=True,
        )

    # No-match cannot include passages
    with pytest.raises(ValidationError):
        KnowledgeRecommendationResponse(
            status=KnowledgeExecutionStatus.NO_MATCH,
            passages=[passage],
            no_match=True,
        )

    # Error requires non-empty error description
    with pytest.raises(ValidationError):
        KnowledgeRecommendationResponse(
            status=KnowledgeExecutionStatus.ERROR,
            error="",
            passages=[],
        )


# ---------------------------------------------------------------------------
# 5. Serialization and Round-Trip Validation (Pydantic v2)
# ---------------------------------------------------------------------------

def test_serialization_and_json_roundtrip():
    """Response serializes to dict and JSON and round-trips without data loss."""
    passage = RetrievedPassage(
        text="Password reset links expire in 30 minutes.",
        source="account_and_password_faq.pdf",
        chunk_id="hash123_p1_c0",
        page=1,
        rank=1,
        score=0.954,
    )
    original = KnowledgeRecommendationResponse.create_success(
        query="password link expiration",
        passages=[passage],
        session_id="sess-auth99",
    )

    # 1. model_dump dict
    dumped_dict = original.model_dump()
    assert isinstance(dumped_dict, dict)
    assert dumped_dict["status"] == "success"
    assert dumped_dict["passages"][0]["score"] == 0.954

    # 2. JSON string serialization
    json_str = original.model_dump_json()
    assert "password link expiration" in json_str

    # 3. Round-trip validation
    reconstructed = KnowledgeRecommendationResponse.model_validate_json(json_str)
    assert reconstructed == original


# ---------------------------------------------------------------------------
# 6. Adapter to Core AgentResult (Orchestrator Contract)
# ---------------------------------------------------------------------------

def test_to_agent_result_compatibility():
    """to_agent_result() produces a valid AgentResult compatible with orchestrator."""
    passage = RetrievedPassage(
        text="Refunds take 5-7 business days.",
        source="returns_and_refunds.pdf",
        rank=1,
        score=0.91,
    )
    resp = KnowledgeRecommendationResponse.create_success(
        query="refund processing days",
        passages=[passage],
        session_id="sess-orch123",
    )

    agent_result = resp.to_agent_result()
    assert isinstance(agent_result, AgentResult)
    assert agent_result.session_id == "sess-orch123"
    assert agent_result.agent_type == "KnowledgeRecommendationAgent"
    assert isinstance(agent_result.result, dict)
    assert agent_result.result["status"] == "success"
    assert len(agent_result.result["passages"]) == 1


# ---------------------------------------------------------------------------
# 7. Agent Execution Integration (Reusing rag_stub)
# ---------------------------------------------------------------------------

def test_agent_run_success():
    """KnowledgeRecommendationAgent produces a success response using rag_stub hits."""
    fake_hits = [
        {
            "text": "Unused items can be returned within 30 days of delivery.",
            "doc_name": "returns_and_refunds.pdf",
            "source": "returns_and_refunds.pdf",
            "page": 1,
            "score": 0.89,
            "chunk_id": "sha_p1_c0",
        }
    ]
    agent = KnowledgeRecommendationAgent()

    with patch("backend.services.rag_stub.retrieve", return_value=fake_hits):
        req = KnowledgeRecommendationRequest(
            message="Can I return an opened box?",
            intent="Refund / billing",
            session_id="sess-live01",
        )
        response = agent.recommend(req)

        assert response.status == KnowledgeExecutionStatus.SUCCESS
        assert len(response.passages) == 1
        assert response.passages[0].source == "returns_and_refunds.pdf"
        assert response.passages[0].rank == 1
        assert response.query == "Refund / billing - Can I return an opened box?"


def test_agent_run_no_match():
    """KnowledgeRecommendationAgent returns no_match when retrieve returns empty."""
    agent = KnowledgeRecommendationAgent()

    with patch("backend.services.rag_stub.retrieve", return_value=[]):
        req = KnowledgeRecommendationRequest(message="Non-existent policy question")
        response = agent.recommend(req)

        assert response.status == KnowledgeExecutionStatus.NO_MATCH
        assert response.no_match is True
        assert response.passages == []


def test_agent_run_handles_exception_safely():
    """KnowledgeRecommendationAgent catches RAG exceptions and returns an error response."""
    agent = KnowledgeRecommendationAgent()

    with patch("backend.services.rag_stub.retrieve", side_effect=RuntimeError("Vector DB offline")):
        req = KnowledgeRecommendationRequest(message="Where is my tracking number?")
        response = agent.recommend(req)

        assert response.status == KnowledgeExecutionStatus.ERROR
        assert "Vector DB offline" in response.error


def test_agent_orchestrator_interface():
    """agent.run(session, message) returns an AgentResult matching the orchestrator contract."""
    session = Session(session_id="sess-orch99", scenario="Delayed package")
    agent = KnowledgeRecommendationAgent()

    fake_hits = [
        {"text": "Shipments arrive in 3-5 days.", "doc_name": "shipping.pdf", "page": 1, "score": 0.8}
    ]
    with patch("backend.services.rag_stub.retrieve", return_value=fake_hits):
        agent_result = agent.run(session=session, message="When will it arrive?")

        assert isinstance(agent_result, AgentResult)
        assert agent_result.session_id == "sess-orch99"
        assert agent_result.result["status"] == "success"
