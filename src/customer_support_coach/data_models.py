import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ValidationError(ValueError):
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
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9_.:-]{1,128}", value
    ):
        raise ValidationError(
            f"{field_name} must contain 1-128 valid ID characters."
        )
    return value

def validate_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            f"{field_name} must be a non-empty string."
        )
    return value.strip()

def validate_timestamp(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValidationError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(
            f"{field_name} must include a timezone."
        )
    return value.astimezone(timezone.utc)

def validate_json_object(value: dict, field_name: str) -> dict:
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
    try:
        return enum_type(value)
    except (ValueError, TypeError):
        allowed = ", ".join(item.value for item in enum_type)
        raise ValidationError(
            f"{field_name} must be one of: {allowed}."
        ) from None

@dataclass
class Session:
    mode: InteractionMode = InteractionMode.SIMULATOR
    product_context: dict[str, Any] = field(default_factory=dict)
    scenario: dict[str, Any] | str | None = None
    customer_persona: dict[str, Any] | str | None = None
    status: SessionStatus = SessionStatus.ACTIVE

    session_id: str = field(
        default_factory=lambda: f"sess-{uuid.uuid4().hex}"
    )
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.session_id = validate_id(self.session_id, "session_id")
        self.mode = _normalize_enum(InteractionMode, self.mode, "mode")
        self.status = _normalize_enum(SessionStatus, self.status, "status")
        self.product_context = validate_json_object(
            self.product_context, "product_context"
        )
        self.metadata = validate_json_object(self.metadata, "metadata")

        if isinstance(self.scenario, str):
            self.scenario = validate_text(self.scenario, "scenario")
        elif isinstance(self.scenario, dict):
            self.scenario = validate_json_object(self.scenario, "scenario")
        elif self.scenario is not None:
            raise ValidationError(
                "scenario must be a string, dictionary, or None."
            )

        if self.mode == InteractionMode.SIMULATOR and self.scenario is None:
            raise ValidationError("scenario is required in simulator mode.")

        if isinstance(self.customer_persona, str):
            self.customer_persona = validate_text(
                self.customer_persona, "customer_persona"
            )
        elif isinstance(self.customer_persona, dict):
            self.customer_persona = validate_json_object(
                self.customer_persona, "customer_persona"
            )
        elif self.customer_persona is not None:
            raise ValidationError(
                "customer_persona must be a string, dictionary, or None."
            )

        self.created_at = validate_timestamp(self.created_at, "created_at")
        self.updated_at = validate_timestamp(self.updated_at, "updated_at")

        if self.updated_at < self.created_at:
            raise ValidationError("updated_at cannot precede created_at.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "mode": self.mode.value,
            "product_context": self.product_context,
            "scenario": self.scenario,
            "customer_persona": self.customer_persona,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

@dataclass
class ConversationMessage:
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
        return {
            "result_id": self.result_id,
            "session_id": self.session_id,
            "message_id": self.message_id,
            "agent_type": self.agent_type,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
        }
