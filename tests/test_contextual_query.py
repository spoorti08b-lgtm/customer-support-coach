"""Focused unit tests for the Contextual Query Builder in Knowledge Recommendation Agent.

Covers Step 4 requirements:
  1. A message with no history.
  2. A message with detected intent.
  3. A follow-up message whose meaning depends on previous customer dialogue.
  4. A history containing multiple topics, ensuring irrelevant topics are not indiscriminately added.
  5. Missing or empty history.
  6. Legacy history objects/dictionaries supported by the existing contract.
  7. Missing product/session context.
  8. Long history, verifying the query remains bounded.
  9. Deterministic output for the same input.
  10. Backward compatibility with existing agent calls.
"""

from __future__ import annotations

from unittest.mock import patch
import pytest

from backend.core.data_models import AgentResult, ConversationMessage, Session, Speaker
from backend.orchestrator.knowledge_schemas import (
    ConversationHistoryItem,
    KnowledgeExecutionStatus,
    KnowledgeRecommendationRequest,
)
from backend.services.knowledge_agent import (
    MAX_QUERY_CHARS,
    KnowledgeRecommendationAgent,
)


@pytest.fixture
def agent():
    return KnowledgeRecommendationAgent()


# ---------------------------------------------------------------------------
# 1. A message with no history
# ---------------------------------------------------------------------------

def test_query_message_with_no_history(agent):
    """When no history is present, query is identical to the cleaned message."""
    req = KnowledgeRecommendationRequest(message="What is the refund window?")
    query = agent.build_query(req)
    assert query == "What is the refund window?"


# ---------------------------------------------------------------------------
# 2. A message with detected intent
# ---------------------------------------------------------------------------

def test_query_message_with_detected_intent(agent):
    """When detected intent is present, it is cleanly prefixed to the message."""
    req = KnowledgeRecommendationRequest(
        message="Can I return an opened box?",
        intent="Refund / billing",
    )
    query = agent.build_query(req)
    assert query == "Refund / billing - Can I return an opened box?"


# ---------------------------------------------------------------------------
# 3. A follow-up message whose meaning depends on previous customer dialogue
# ---------------------------------------------------------------------------

def test_query_followup_resolves_pronoun_from_previous_dialogue(agent):
    """Follow-up questions with pronouns resolve context from prior customer turn."""
    req = KnowledgeRecommendationRequest(
        message="How long do I have to send it back?",
        history=[
            ConversationHistoryItem(
                speaker="customer",
                content="I received a damaged coffee maker yesterday.",
                turn_number=1,
            ),
            ConversationHistoryItem(
                speaker="agent",
                content="I'm sorry to hear that. I can assist with replacement or refund.",
                turn_number=2,
            ),
        ],
    )
    query = agent.build_query(req)

    # Must preserve current message and include reference to the damaged item
    assert "How long do I have to send it back?" in query
    assert "damaged coffee maker" in query.lower()
    assert "(re:" in query


# ---------------------------------------------------------------------------
# 4. A history containing multiple topics (irrelevant topics excluded)
# ---------------------------------------------------------------------------

def test_query_multi_topic_history_filters_irrelevant_topics(agent):
    """When history contains multiple past topics, only the relevant domain is added."""
    req = KnowledgeRecommendationRequest(
        message="How many failed attempts lock the account?",
        history=[
            # Topic 1: Shoes / return (irrelevant to account lockout)
            ConversationHistoryItem(
                speaker="customer",
                content="I bought running shoes last week and need a return label.",
                turn_number=1,
            ),
            ConversationHistoryItem(
                speaker="agent",
                content="Sure, I can help you return the shoes.",
                turn_number=2,
            ),
            # Topic 2: Account security (relevant to current message)
            ConversationHistoryItem(
                speaker="customer",
                content="Now I cannot log in and my profile says locked.",
                turn_number=3,
            ),
        ],
    )
    query = agent.build_query(req)

    assert "How many failed attempts lock the account?" in query
    # Must NOT mention running shoes or return
    assert "shoes" not in query.lower()
    assert "return label" not in query.lower()
    # Must connect to the relevant account issue
    assert "profile says locked" in query.lower() or "cannot log in" in query.lower()


# ---------------------------------------------------------------------------
# 5. Missing or empty history
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("empty_val", [[], None])
def test_query_missing_or_empty_history(agent, empty_val):
    """Missing or empty history falls back to the current message without error."""
    req = KnowledgeRecommendationRequest(
        message="Where is my tracking number?",
        history=empty_val or [],
    )
    query = agent.build_query(req)
    assert query == "Where is my tracking number?"


# ---------------------------------------------------------------------------
# 6. Legacy history objects and dictionaries
# ---------------------------------------------------------------------------

def test_query_supports_legacy_history_formats(agent):
    """Supports both ConversationMessage dataclasses and legacy role/text dicts."""
    # Dict format (role/text)
    req_dict = KnowledgeRecommendationRequest(
        message="Can I exchange them?",
        history=[
            {"role": "customer", "text": "I ordered leather boots in size 9."},
            {"role": "agent", "text": "We offer exchanges within 30 days."},
        ],
    )
    query_dict = agent.build_query(req_dict)
    assert "leather boots" in query_dict.lower()

    # Dataclass format (ConversationMessage)
    msg = ConversationMessage(
        session_id="sess-legacy1",
        speaker=Speaker.CUSTOMER,
        content="I ordered wireless earbuds yesterday.",
        turn_number=1,
    )
    req_obj = KnowledgeRecommendationRequest(
        message="What is the warranty period?",
        history=[msg],
    )
    query_obj = agent.build_query(req_obj)
    assert "wireless earbuds" in query_obj.lower()


# ---------------------------------------------------------------------------
# 7. Missing product / session context
# ---------------------------------------------------------------------------

def test_query_missing_product_context_does_not_invent_product(agent):
    """When product context is missing, no product name is fabricated."""
    req = KnowledgeRecommendationRequest(
        message="What are your support hours?",
        product=None,
    )
    query = agent.build_query(req, session=None)
    assert query == "What are your support hours?"
    assert "acme" not in query.lower()
    assert "product" not in query.lower()


def test_query_with_supplied_product_context(agent):
    """When product context is provided, it is prepended cleanly."""
    req = KnowledgeRecommendationRequest(
        message="How do I update firmware?",
        product="Smart Hub 3000",
    )
    query = agent.build_query(req)
    assert query.startswith("Smart Hub 3000 - ")
    assert "How do I update firmware?" in query


# ---------------------------------------------------------------------------
# 8. Long history (query remains bounded)
# ---------------------------------------------------------------------------

def test_query_remains_strictly_bounded_on_long_history(agent):
    """Even with extensive dialogue, the synthesized query never exceeds maximum bound."""
    long_history = []
    for i in range(1, 25):
        long_history.append(
            ConversationHistoryItem(
                speaker="customer" if i % 2 == 1 else "agent",
                content=f"Detailed message turn #{i} discussing long warranty clauses and policy details " * 4,
                turn_number=i,
            )
        )

    req = KnowledgeRecommendationRequest(
        message="Can I get an extension on the warranty period?",
        intent="Warranty / support",
        product="Enterprise Server Pro X",
        history=long_history,
    )
    query = agent.build_query(req)

    assert len(query) <= MAX_QUERY_CHARS
    assert "Enterprise Server Pro X" in query
    assert "Can I get an extension" in query


# ---------------------------------------------------------------------------
# 9. Deterministic output for the same input
# ---------------------------------------------------------------------------

def test_query_is_deterministic(agent):
    """Repeated calls with identical request inputs produce byte-identical queries."""
    req = KnowledgeRecommendationRequest(
        message="Can I change delivery address?",
        intent="Shipping / delivery",
        product="Acme Gadgets",
        history=[
            {"role": "customer", "text": "I placed order #9821 this morning."},
            {"role": "agent", "text": "Let me check the status."},
        ],
    )

    baseline = agent.build_query(req)
    for _ in range(50):
        assert agent.build_query(req) == baseline


# ---------------------------------------------------------------------------
# 10. Backward compatibility with existing agent calls
# ---------------------------------------------------------------------------

def test_agent_backward_compatibility_run_and_recommend(agent):
    """Existing agent interfaces (recommend, run) operate seamlessly with contextual queries."""
    fake_hits = [
        {
            "text": "Shipping addresses can be modified within 1 hour of placing the order.",
            "doc_name": "shipping_and_delivery.pdf",
            "source": "shipping_and_delivery.pdf",
            "page": 1,
            "score": 0.85,
        }
    ]

    with patch("backend.services.rag_stub.retrieve", return_value=fake_hits):
        # 1. recommend() with request
        req = KnowledgeRecommendationRequest(
            message="Can I change the shipping address?",
            intent="Shipping / delivery",
        )
        resp = agent.recommend(req)
        assert resp.status == KnowledgeExecutionStatus.SUCCESS
        assert len(resp.passages) == 1
        assert resp.passages[0].score == 0.85

        # 2. run() with Session and message
        session = Session(session_id="sess-comp1", product="Acme Online Store")
        agent_result = agent.run(session=session, message="Can I change shipping address?")
        assert isinstance(agent_result, AgentResult)
        assert agent_result.session_id == "sess-comp1"
        assert agent_result.result["status"] == "success"
