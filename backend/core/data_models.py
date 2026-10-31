"""
Shared Data Models and Validation
Developed by Vikas M
Infosys Springboard Virtual Internship 7.0
Project: AI Customer Support Coaching Assistant

NOTE: Core shared data models.
      It is copied here temporarily so the Orchestrator
      module can be developed and tested independently.
      Replace with the real import once the team merges.
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ValidationError(ValueError):
    """Raised when input data violates model validation rules."""


class InteractionMode(str, Enum):
    SIMULATOR = "simulator"
    MANUAL = "manual"
    REPLAY = "replay"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Speaker(str, Enum):
    CUSTOMER = "customer"
    AGENT = "agent"
    SYSTEM = "system"


def validate_id(value: str, field_name: str) -> str:
    """Validate an identifier containing 1-128 permitted characters."""
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9_.:-]{1,128}", value
    ):
        raise ValidationError(
            f"{field_name} must contain 1-128 valid ID characters."
        )
    return value


def validate_text(value: str, field_name: str) -> str:
    """Require non-empty text and remove surrounding whitespace."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            f"{field_name} must be a non-empty string."
        )
    return value.strip()


def validate_timestamp(value: datetime, field_name: str) -> datetime:
    """Require a timezone-aware datetime and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise ValidationError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(
            f"{field_name} must include a timezone."
        )

    return value.astimezone(timezone.utc)


def validate_json_object(value: dict, field_name: str) -> dict:
    """Require a dictionary containing strict JSON-compatible data."""
    if not isinstance(value, dict):
        raise ValidationError(f"{field_name} must be a dictionary.")

    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        raise ValidationError(
            f"{field_name} must contain valid JSON-serializable data."
        ) from None

    return value


def _normalize_enum(enum_type: type[Enum], value: Any, field_name: str):
    """Convert a valid enum value or raise a consistent validation error."""
    try:
        return enum_type(value)
    except (ValueError, TypeError):
        allowed = ", ".join(item.value for item in enum_type)
        raise ValidationError(
            f"{field_name} must be one of: {allowed}."
        ) from None


@dataclass
class Session:
    """Represents one customer-support training session (flat Milestone 1 schema)."""

    session_id: str = field(
        default_factory=lambda: f"sess-{uuid.uuid4().hex[:8]}"
    )
    mode: InteractionMode | str = "Simulator"
    product: str = "Acme Online Store"
    scenario: str | None = None
    persona: str | None = None
    max_turns: int | None = None
    replay_transcript: list[dict[str, str]] | None = None
    kb_documents: list[str] = field(default_factory=list)
    status: str = "configured"
    created_at: str | datetime = field(
        default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds")
    )

    # Legacy fields accepted for backward compatibility with orchestrator / tests
    product_context: dict[str, Any] | None = None
    customer_persona: str | None = None
    updated_at: datetime | str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.session_id = validate_id(self.session_id, "session_id")

        if isinstance(self.mode, InteractionMode):
            mode_str = self.mode.value.capitalize()
        else:
            mode_str = str(self.mode).capitalize()
        if mode_str in ("Simulator", "Manual", "Replay"):
            self.mode = mode_str
        else:
            self.mode = "Simulator"

        if self.product_context and isinstance(self.product_context, dict):
            if not self.product or self.product == "Acme Online Store":
                self.product = self.product_context.get("product", self.product)

        if not self.persona:
            if self.customer_persona:
                self.persona = str(self.customer_persona)
            elif self.metadata and "persona" in self.metadata:
                self.persona = str(self.metadata["persona"])

        if self.mode == "Simulator":
            if not self.persona:
                self.persona = "Calm"
            if not self.max_turns:
                self.max_turns = self.metadata.get("max_turns", 5) if self.metadata else 5
        else:
            self.persona = None
            self.max_turns = None

        if self.mode == "Replay":
            if self.replay_transcript is None and self.metadata and "replay_script" in self.metadata:
                self.replay_transcript = self.metadata["replay_script"]
        else:
            self.replay_transcript = None

        if isinstance(self.created_at, datetime):
            self.created_at = self.created_at.astimezone().isoformat(timespec="seconds")
        elif not isinstance(self.created_at, str):
            self.created_at = datetime.now().astimezone().isoformat(timespec="seconds")

    def to_dict(self) -> dict[str, Any]:
        """Convert the session into JSON conforming to the flat schema."""
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "product": self.product,
            "scenario": self.scenario,
            "persona": self.persona,
            "max_turns": self.max_turns,
            "replay_transcript": self.replay_transcript,
            "kb_documents": list(self.kb_documents),
            "status": "configured",
            "created_at": self.created_at,
        }


@dataclass
class ConversationMessage:
    """Represents one message in a conversation."""

    session_id: str
    speaker: Speaker
    content: str
    turn_number: int

    message_id: str = field(
        default_factory=lambda: f"msg-{uuid.uuid4().hex}"
    )
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.session_id = validate_id(self.session_id, "session_id")
        self.message_id = validate_id(self.message_id, "message_id")
        self.content = validate_text(self.content, "content")
        self.speaker = _normalize_enum(Speaker, self.speaker, "speaker")

        if (
            isinstance(self.turn_number, bool)
            or not isinstance(self.turn_number, int)
            or self.turn_number < 1
        ):
            raise ValidationError("turn_number must be a positive integer.")

        self.timestamp = validate_timestamp(self.timestamp, "timestamp")
        self.metadata = validate_json_object(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert the message into JSON-compatible data."""
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "speaker": self.speaker.value,
            "content": self.content,
            "turn_number": self.turn_number,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class AgentResult:
    """Stores the result produced by an AI agent."""

    session_id: str
    agent_type: str
    result: dict[str, Any]

    result_id: str = field(
        default_factory=lambda: f"res-{uuid.uuid4().hex}"
    )
    message_id: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self):
        self.session_id = validate_id(self.session_id, "session_id")
        self.result_id = validate_id(self.result_id, "result_id")

        if self.message_id is not None:
            self.message_id = validate_id(self.message_id, "message_id")

        self.agent_type = validate_text(self.agent_type, "agent_type")
        self.result = validate_json_object(self.result, "result")
        self.created_at = validate_timestamp(self.created_at, "created_at")

    def to_dict(self) -> dict[str, Any]:
        """Convert the agent result into JSON-compatible data."""
        return {
            "result_id": self.result_id,
            "session_id": self.session_id,
            "message_id": self.message_id,
            "agent_type": self.agent_type,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
        }
