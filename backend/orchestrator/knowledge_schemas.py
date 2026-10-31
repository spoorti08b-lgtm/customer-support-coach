"""Knowledge Recommendation Agent input and output schemas.

Provides strict Pydantic v2 data contracts for the Knowledge Recommendation
Agent, supporting distinct success, no-match, and error
outcomes, input validation, and bidirectional compatibility with the shared
orchestrator and AgentResult data models.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.core.data_models import Speaker


class KnowledgeExecutionStatus(str, Enum):
    """Execution status of the Knowledge Recommendation Agent."""

    SUCCESS = "success"
    NO_MATCH = "no_match"
    ERROR = "error"


class ConversationHistoryItem(BaseModel):
    """Represents a prior turn in the conversation for context-aware retrieval."""

    model_config = ConfigDict(extra="ignore")

    speaker: str = Field(
        default="customer",
        description="Speaker role identifier ('customer', 'agent', or 'system').",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Message text content of the conversation turn.",
    )
    turn_number: int | None = Field(
        default=None,
        ge=1,
        description="Optional 1-indexed turn number.",
    )

    @field_validator("content", mode="before")
    @classmethod
    def content_must_not_be_whitespace(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Message content must not be empty or whitespace-only.")
        return value.strip()

    @field_validator("speaker")
    @classmethod
    def normalize_speaker(cls, value: Any) -> str:
        if isinstance(value, Speaker):
            return value.value
        if hasattr(value, "value"):
            value = value.value
        val_str = str(value).strip().lower()
        if val_str not in ("customer", "agent", "system"):
            raise ValueError(
                f"speaker must be one of 'customer', 'agent', 'system'; got '{value}'"
            )
        return val_str


class KnowledgeRecommendationRequest(BaseModel):
    """Input contract for the Knowledge Recommendation Agent.

    Required fields:
        - message: The customer's latest incoming message.

    Optional fields:
        - intent: Extracted customer intent from upstream intent agent.
        - product: Product or service name from session context.
        - history: Relevant prior conversation turns.
        - session_id: Identifier of the active session (1-128 chars).
        - kb_identifier: Vector collection name (defaults to 'support_kb').
        - limit: Maximum number of passages to retrieve (1-20, default: 3).
    """

    model_config = ConfigDict(extra="ignore")

    message: str = Field(
        ...,
        min_length=1,
        description="Customer's current message to search knowledge against.",
    )
    intent: str | None = Field(
        default=None,
        description="Detected intent category (e.g. 'Refund / billing', 'Delivery / order').",
    )
    product: str | None = Field(
        default=None,
        description="Product or service name from session context.",
    )
    history: list[ConversationHistoryItem] = Field(
        default_factory=list,
        description="Relevant conversation history turns for multi-turn context.",
    )
    session_id: str | None = Field(
        default=None,
        max_length=128,
        description="Session identifier conforming to standard 1-128 ID chars.",
    )
    kb_identifier: str = Field(
        default="support_kb",
        min_length=1,
        max_length=128,
        description="Knowledge base vector collection identifier.",
    )
    limit: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Configurable retrieval limit (default: 3, range: 1-20).",
    )

    @field_validator("message", mode="before")
    @classmethod
    def message_must_not_be_whitespace(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Customer message must not be empty or whitespace-only.")
        return value.strip()

    @field_validator("intent")
    @classmethod
    def clean_intent(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @field_validator("product")
    @classmethod
    def clean_product(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        if not clean:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", clean):
            raise ValueError(
                "session_id must contain 1-128 valid ID characters (letters, digits, _.:-)."
            )
        return clean

    @field_validator("history", mode="before")
    @classmethod
    def coerce_history(cls, raw: Any) -> Any:
        """Tolerantly accept list of dicts, ConversationMessage dataclasses, or models."""
        if not isinstance(raw, list):
            return raw
        normalized = []
        for item in raw:
            if hasattr(item, "to_dict"):
                item = item.to_dict()
            if isinstance(item, dict):
                speaker = item.get("speaker") or item.get("role") or "customer"
                content = item.get("content") or item.get("text") or ""
                turn = item.get("turn_number") or item.get("turn")
                normalized.append({
                    "speaker": speaker,
                    "content": content,
                    "turn_number": turn,
                })
            else:
                normalized.append(item)
        return normalized


class RetrievedPassage(BaseModel):
    """Structured representation of one retrieved policy or FAQ passage."""

    model_config = ConfigDict(extra="ignore")

    text: str = Field(
        ...,
        min_length=1,
        description="Passage text content retrieved from the knowledge base.",
    )
    source: str = Field(
        ...,
        min_length=1,
        description="Original source filename (e.g. 'returns_and_refunds.pdf').",
    )
    doc_name: str | None = Field(
        default=None,
        description="Document name alias matching ChromaDB metadata.",
    )
    chunk_id: str | None = Field(
        default=None,
        description="Deterministic chunk identifier (<hash>_p<page>_c<idx>).",
    )
    page: int | None = Field(
        default=None,
        ge=1,
        description="1-indexed source document page number.",
    )
    rank: int = Field(
        ...,
        ge=1,
        description="1-indexed ranking position in search results.",
    )
    score: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Normalized cosine similarity score (1.0 - distance).",
    )

    @model_validator(mode="after")
    def sync_doc_name(self) -> RetrievedPassage:
        if self.doc_name is None:
            self.doc_name = self.source
        return self


class KnowledgeRecommendationResponse(BaseModel):
    """Structured result returned by the Knowledge Recommendation Agent.

    Supports three distinct outcomes:
      - 'success': One or more matching passages retrieved; no_match=False, error=None.
      - 'no_match': Clean execution but zero relevant passages found; no_match=True, passages=[], error=None.
      - 'error': Agent encountered an execution or RAG failure; error describes what went wrong, passages=[].
    """

    model_config = ConfigDict(extra="ignore")

    agent_name: str = Field(
        default="KnowledgeRecommendationAgent",
        description="Identifier of the executing recommendation agent.",
    )
    status: KnowledgeExecutionStatus = Field(
        ...,
        description="Execution status outcome ('success', 'no_match', or 'error').",
    )
    query: str = Field(
        default="",
        description="Effective search query used for vector retrieval.",
    )
    passages: list[RetrievedPassage] = Field(
        default_factory=list,
        description="Ranked list of retrieved knowledge passages.",
    )
    no_match: bool = Field(
        default=False,
        description="True when no relevant passages met the threshold or knowledge base was empty.",
    )
    error: str | None = Field(
        default=None,
        description="Error description if status is 'error'; None on success or clean no-match.",
    )
    session_id: str | None = Field(
        default=None,
        max_length=128,
        description="Session ID associated with the request.",
    )

    @model_validator(mode="after")
    def validate_outcome_consistency(self) -> KnowledgeRecommendationResponse:
        """Enforce strict semantic consistency across distinct outcomes."""
        if self.status == KnowledgeExecutionStatus.SUCCESS:
            if not self.passages:
                raise ValueError("Status 'success' requires at least one retrieved passage.")
            if self.no_match:
                raise ValueError("Status 'success' cannot have no_match=True.")
            if self.error is not None:
                raise ValueError("Status 'success' cannot contain an error message.")
        elif self.status == KnowledgeExecutionStatus.NO_MATCH:
            if self.passages:
                raise ValueError("Status 'no_match' must have empty passages.")
            if not self.no_match:
                raise ValueError("Status 'no_match' must have no_match=True.")
            if self.error is not None:
                raise ValueError("Status 'no_match' cannot contain an error message.")
        elif self.status == KnowledgeExecutionStatus.ERROR:
            if not self.error or not self.error.strip():
                raise ValueError("Status 'error' requires a non-empty error description.")
            if self.passages:
                raise ValueError("Status 'error' must have empty passages.")
        return self

    @classmethod
    def create_success(
        cls,
        query: str,
        passages: list[RetrievedPassage],
        session_id: str | None = None,
        agent_name: str = "KnowledgeRecommendationAgent",
    ) -> KnowledgeRecommendationResponse:
        """Factory for a successful recommendation outcome."""
        return cls(
            agent_name=agent_name,
            status=KnowledgeExecutionStatus.SUCCESS,
            query=query,
            passages=passages,
            no_match=False,
            error=None,
            session_id=session_id,
        )

    @classmethod
    def create_no_match(
        cls,
        query: str,
        session_id: str | None = None,
        agent_name: str = "KnowledgeRecommendationAgent",
    ) -> KnowledgeRecommendationResponse:
        """Factory for a clean no-match recommendation outcome."""
        return cls(
            agent_name=agent_name,
            status=KnowledgeExecutionStatus.NO_MATCH,
            query=query,
            passages=[],
            no_match=True,
            error=None,
            session_id=session_id,
        )

    @classmethod
    def create_error(
        cls,
        error_message: str,
        query: str = "",
        session_id: str | None = None,
        agent_name: str = "KnowledgeRecommendationAgent",
    ) -> KnowledgeRecommendationResponse:
        """Factory for an error recommendation outcome."""
        return cls(
            agent_name=agent_name,
            status=KnowledgeExecutionStatus.ERROR,
            query=query,
            passages=[],
            no_match=False,
            error=error_message,
            session_id=session_id,
        )

    def to_agent_result(self, session_id: str | None = None) -> Any:
        """Export to the shared AgentResult dataclass for orchestrator compatibility."""
        from backend.core.data_models import AgentResult

        sid = session_id or self.session_id or "sess-default"
        return AgentResult(
            session_id=sid,
            agent_type=self.agent_name,
            result=self.model_dump(),
        )
