"""Knowledge Recommendation Agent implementation.

Consumes the KnowledgeRecommendationRequest and KnowledgeRecommendationResponse
Pydantic contracts while reusing the single verified local ChromaDB RAG
retrieval pipeline in backend.services.rag_stub.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.core.data_models import AgentResult, Session
from backend.orchestrator.knowledge_schemas import (
    ConversationHistoryItem,
    KnowledgeExecutionStatus,
    KnowledgeRecommendationRequest,
    KnowledgeRecommendationResponse,
    RetrievedPassage,
)
from backend.services import rag_stub

logger = logging.getLogger(__name__)

# Domain keyword clusters for relevance matching
DOMAINS: dict[str, set[str]] = {
    "refund": {
        "refund", "refunds", "return", "returns", "exchange", "damaged",
        "faulty", "replacement", "warranty", "money", "package", "packaging",
        "box", "label", "prepaid", "policy", "days",
    },
    "account": {
        "password", "account", "login", "locked", "signin", "sign-in",
        "email", "2fa", "two-step", "verification", "profile", "reset",
        "code", "authenticator", "security", "credentials",
    },
    "shipping": {
        "shipping", "ship", "delivery", "delivered", "order", "parcel",
        "tracking", "courier", "dispatch", "late", "arrive", "address",
        "transit", "post", "carrier",
    },
    "billing": {
        "billing", "charge", "charged", "invoice", "payment", "card",
        "fee", "cost", "receipt", "deducted", "double", "duplicate",
    },
}

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "i", "my", "me", "you",
    "your", "we", "our", "to", "for", "in", "on", "at", "by", "from",
    "and", "or", "so", "it", "this", "that", "do", "does", "did", "can",
    "could", "would", "should", "have", "has", "had", "hello", "hi",
    "hey", "please", "thanks", "thank",
}

PRONOUN_REF_WORDS = {
    "it", "its", "this", "that", "these", "those", "them", "there", "they",
}

MAX_QUERY_CHARS = 220
MAX_CLUE_CHARS = 55


def _get_text_domains(text: str) -> set[str]:
    """Identify support domain categories mentioned in a text snippet."""
    tokens = set(re.findall(r"\b\w+\b", text.lower()))
    return {domain for domain, keywords in DOMAINS.items() if tokens & keywords}


def _extract_salient_clue(text: str) -> str:
    """Extract a concise, informative subject/clue from a prior customer turn."""
    cleaned = re.sub(
        r"^(hi|hello|hey|good morning|good afternoon|good evening|dear support)[,.\s!]*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r"^(also|please note that|i want to say that|i just want to let you know that)[,.\s!]*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    cleaned = " ".join(cleaned.split())

    if len(cleaned) <= MAX_CLUE_CHARS:
        return cleaned

    truncated = cleaned[:MAX_CLUE_CHARS]
    last_space = truncated.rfind(" ")
    if last_space > 20:
        truncated = truncated[:last_space]
    return truncated.rstrip(",. ;:")


def _is_relevant_turn(
    turn_text: str,
    current_message: str,
    intent: str | None,
) -> bool:
    """Determine whether a past customer turn is contextually relevant to the current query."""
    clean_turn = turn_text.strip().lower()
    clean_curr = current_message.strip().lower()

    if not clean_turn or not clean_curr:
        return False

    curr_domains = _get_text_domains(clean_curr)
    if intent:
        curr_domains |= _get_text_domains(intent)
    turn_domains = _get_text_domains(clean_turn)

    # 1. Domain-level check
    if curr_domains and turn_domains:
        if curr_domains & turn_domains:
            return True
        # Completely disjoint known domains -> irrelevant topic
        return False

    # 2. Check lexical overlap
    curr_words = set(re.findall(r"\b[a-z]{3,}\b", clean_curr)) - STOP_WORDS
    turn_words = set(re.findall(r"\b[a-z]{3,}\b", clean_turn)) - STOP_WORDS
    if curr_words & turn_words:
        return True

    # 3. Check anaphoric reference
    all_curr_tokens = set(re.findall(r"\b\w+\b", clean_curr))
    has_pronoun = bool(all_curr_tokens & PRONOUN_REF_WORDS)
    is_short = len(clean_curr.split()) <= 7

    if (has_pronoun or is_short) and not (curr_domains and turn_domains and not (curr_domains & turn_domains)):
        return True

    return False


class KnowledgeRecommendationAgent:
    """Knowledge Recommendation Agent for frontline coaching.

    Retrieves relevant policy and support documentation chunks using dense
    vector search over ChromaDB and returns structured recommendations conforming
    to the Milestone 2 input/output contract.
    """

    AGENT_TYPE = "knowledge-recommendation-agent"

    def __init__(
        self,
        default_limit: int = 3,
        min_score_threshold: float = 0.20,
    ) -> None:
        self.default_limit = default_limit
        self.min_score_threshold = min_score_threshold

    def build_query(
        self,
        request: KnowledgeRecommendationRequest,
        session: Session | None = None,
    ) -> str:
        """Construct a context-aware retrieval query using message, intent, product, and history."""
        curr_msg = request.message.strip()

        # 1. Resolve product name from request or session context
        product = request.product
        if not product and session:
            product = getattr(session, "product", None)
        if product:
            product = str(product).strip()

        # 2. Extract recent relevant customer dialogue
        history = request.history or []
        customer_turns: list[str] = []
        for item in history:
            speaker = getattr(item, "speaker", None)
            if speaker is None and isinstance(item, dict):
                speaker = item.get("speaker") or item.get("role")
            if str(speaker).lower() in ("customer", "user"):
                content = getattr(item, "content", None)
                if content is None and isinstance(item, dict):
                    content = item.get("content") or item.get("text")
                if content and str(content).strip():
                    customer_turns.append(str(content).strip())

        relevant_clue: str | None = None
        for turn_text in reversed(customer_turns):
            if _is_relevant_turn(turn_text, curr_msg, request.intent):
                clue = _extract_salient_clue(turn_text)
                if clue and clue.lower() not in curr_msg.lower():
                    relevant_clue = clue
                    break

        # 3. Assemble query prefix (product, intent)
        prefix_parts: list[str] = []
        if product and product.lower() not in curr_msg.lower():
            prefix_parts.append(product)
        if request.intent and request.intent.lower() not in curr_msg.lower():
            prefix_parts.append(request.intent)

        if prefix_parts:
            base_query = f"{' - '.join(prefix_parts)} - {curr_msg}"
        else:
            base_query = curr_msg

        if relevant_clue:
            synthesized = f"{base_query} (re: {relevant_clue})"
        else:
            synthesized = base_query

        # 4. Strict length bounding
        if len(synthesized) > MAX_QUERY_CHARS:
            truncated = synthesized[:MAX_QUERY_CHARS]
            last_space = truncated.rfind(" ")
            if last_space > MAX_QUERY_CHARS // 2:
                synthesized = truncated[:last_space]
            else:
                synthesized = truncated

        return synthesized

    def recommend(
        self,
        request: KnowledgeRecommendationRequest,
        session: Session | None = None,
    ) -> KnowledgeRecommendationResponse:
        """Execute knowledge retrieval against ChromaDB and return structured response."""
        query = self.build_query(request, session=session)
        limit = request.limit or self.default_limit

        try:
            hits = rag_stub.retrieve(query=query, k=limit)
        except Exception as exc:
            logger.exception("Knowledge retrieval failed for query: %s", query)
            return KnowledgeRecommendationResponse.create_error(
                error_message=f"Knowledge retrieval error: {exc}",
                query=query,
                session_id=request.session_id,
                agent_name=self.AGENT_TYPE,
            )

        if not hits:
            return KnowledgeRecommendationResponse.create_no_match(
                query=query,
                session_id=request.session_id,
                agent_name=self.AGENT_TYPE,
            )

        passages: list[RetrievedPassage] = []
        for idx, hit in enumerate(hits, start=1):
            score = hit.get("score")
            if score is not None and score < self.min_score_threshold:
                continue

            doc_name = hit.get("doc_name") or hit.get("source", "unknown.pdf")
            passages.append(
                RetrievedPassage(
                    text=hit.get("text", ""),
                    source=doc_name,
                    doc_name=doc_name,
                    chunk_id=hit.get("chunk_id"),
                    page=hit.get("page", 1),
                    rank=idx,
                    score=score,
                )
            )

        if not passages:
            return KnowledgeRecommendationResponse.create_no_match(
                query=query,
                session_id=request.session_id,
                agent_name=self.AGENT_TYPE,
            )

        return KnowledgeRecommendationResponse.create_success(
            query=query,
            passages=passages,
            session_id=request.session_id,
            agent_name=self.AGENT_TYPE,
        )

    def run(self, session: Session, message: str) -> AgentResult:
        """Standard orchestrator agent entry point: agent.run(session, message) -> AgentResult."""
        try:
            product = getattr(session, "product", None) if session else None
            req = KnowledgeRecommendationRequest(
                message=message,
                session_id=session.session_id if session else None,
                product=product,
                limit=self.default_limit,
            )
            response = self.recommend(req, session=session)
        except Exception as exc:
            logger.exception("Knowledge recommendation agent failed")
            response = KnowledgeRecommendationResponse.create_error(
                error_message=f"Agent error: {exc}",
                query=message,
                session_id=session.session_id if session else None,
                agent_name=self.AGENT_TYPE,
            )

        return response.to_agent_result(session_id=session.session_id if session else None)
