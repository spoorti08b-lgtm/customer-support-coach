"""Shared Pydantic v2 contracts for Milestone 2 agents."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.orchestrator.knowledge_schemas import (
    ConversationHistoryItem,
    KnowledgeRecommendationResponse,
)


class CustomerMessage(BaseModel):
    """A customer message produced by the simulator or supplied by a user."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    turn_number: int = Field(ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be empty or whitespace-only")
        return value


class SimulatorInput(BaseModel):
    """Input contract for the Customer Simulator Agent."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    persona: str = Field(min_length=1)
    history: list[ConversationHistoryItem] = Field(default_factory=list)
    turn_number: int = Field(ge=1)
    max_turns: int = Field(ge=1)


class SimulatorOutput(BaseModel):
    """Output contract for the Customer Simulator Agent."""

    model_config = ConfigDict(extra="forbid")

    message: CustomerMessage
    is_final: bool = False


class SentimentResult(BaseModel):
    """Structured sentiment and intent analysis for a customer message."""

    model_config = ConfigDict(extra="forbid")

    sentiment: Literal["positive", "neutral", "negative", "mixed"]
    confidence: float = Field(ge=0.0, le=1.0)
    intent: str | None = None
    intent_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class AgentError(BaseModel):
    """Consistent error details returned by an agent or workflow."""

    model_config = ConfigDict(extra="forbid")

    agent_name: str = Field(min_length=1)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class TurnResult(BaseModel):
    """Combined result for one customer-support conversation turn."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    turn_number: int = Field(ge=1)
    customer_message: CustomerMessage
    sentiment: SentimentResult | None = None
    knowledge: KnowledgeRecommendationResponse | None = None
    status: Literal["completed", "partial", "failed"]
    errors: list[AgentError] = Field(default_factory=list)


__all__ = [
    "CustomerMessage",
    "SimulatorInput",
    "SimulatorOutput",
    "SentimentResult",
    "TurnResult",
    "AgentError",
]
