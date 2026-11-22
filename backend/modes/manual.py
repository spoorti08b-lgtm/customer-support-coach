"""Manual Mode turn handling: validation, analysis and duplicate prevention.

The functions here operate on a session mapping (the Streamlit
``session_state`` in the UI, a plain dict in tests) so Manual Mode can be
tested without rendering anything.  They are the only place that appends
Manual Mode turns, which keeps message ordering, message ids and session
isolation in one tested place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, MutableMapping

from backend.modes import coaching
from utils.validation import validate_message

MAX_MESSAGE_CHARS = 1500

_SESSION_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_WHITESPACE = re.compile(r"\s+")
_MODE = "Manual"


@dataclass
class TurnOutcome:
    """Result of one submitted turn."""

    ok: bool
    message: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    tone: dict[str, Any] | None = None
    error: str | None = None
    duplicate: bool = False
    invalid_session: bool = False


def valid_session_id(session_id: Any) -> bool:
    """True when ``session_id`` is a safe, non-empty session identifier."""
    return isinstance(session_id, str) and bool(_SESSION_ID.fullmatch(session_id))


def normalize_text(text: Any) -> str:
    """Normalise text for duplicate checks.

    Whitespace and case are ignored so a double submit, a refresh, or a
    trivially reworded casing is not recorded as a new conversation turn.
    """
    return _WHITESPACE.sub(" ", str(text or "")).strip().casefold()


def _messages(session: MutableMapping[str, Any]) -> list[dict[str, Any]]:
    messages = session.get("messages")
    if not isinstance(messages, list):
        messages = []
        session["messages"] = messages
    return messages


def _analyses(session: MutableMapping[str, Any]) -> list[dict[str, Any]]:
    analyses = session.get("analyses")
    if not isinstance(analyses, list):
        analyses = []
        session["analyses"] = analyses
    return analyses


def _tones(session: MutableMapping[str, Any]) -> list[dict[str, Any]]:
    tones = session.get("tone")
    if not isinstance(tones, list):
        tones = []
        session["tone"] = tones
    return tones


def next_message_id(session: MutableMapping[str, Any]) -> str:
    """Return a stable per-session message id."""
    return f"msg-{len(_messages(session)) + 1:04d}"


def is_duplicate(
    messages: list[dict[str, Any]],
    role: str,
    text: str,
) -> bool:
    """Detect a repeated submission of the immediately preceding turn.

    A customer repeating themselves after an agent reply is a legitimate
    signal and is allowed; the same text arriving twice in a row with no
    turn in between is treated as a double submit/refresh.
    """
    if not messages:
        return False
    last = messages[-1]
    return (
        str(last.get("role")) == role
        and normalize_text(last.get("text")) == normalize_text(text)
    )


def _check_session(session: MutableMapping[str, Any]) -> str | None:
    session_id = session.get("sid")
    if not session_id:
        return (
            "This session is not active. Start a new coaching session from "
            "the setup page."
        )
    if not valid_session_id(session_id):
        return (
            "The session id is invalid. Saved sessions use letters, digits, "
            "dots, colons, dashes and underscores."
        )
    config = session.get("config") or {}
    if str(config.get("mode")) != _MODE:
        return f"Manual Mode is not active for this session (mode: {config.get('mode')})."
    return None


def _analyze(
    text: str,
    history: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return coaching.analyze_customer_turn(text, history, config), None
    except Exception as exc:
        return None, (
            "Coaching analysis failed for this message, so no coaching "
            f"output is shown. ({exc.__class__.__name__}: {exc})"
        )


def submit_customer_message(
    session: MutableMapping[str, Any],
    text: str,
) -> TurnOutcome:
    """Validate and record one pasted customer message.

    The message and its analysis are appended only when validation passes.
    A failed analysis still records the message (the conversation is real)
    but returns ``error`` instead of inventing coaching output.
    """
    problem = _check_session(session)
    if problem:
        return TurnOutcome(ok=False, error=problem, invalid_session=True)

    error = validate_message(text, "Customer message", MAX_MESSAGE_CHARS)
    if error:
        return TurnOutcome(ok=False, error=error)

    message_text = str(text).strip()
    messages = _messages(session)

    if is_duplicate(messages, "customer", message_text):
        return TurnOutcome(
            ok=False,
            error="That message was already submitted. Send a new customer message.",
            duplicate=True,
        )

    message = {
        "id": next_message_id(session),
        "role": "customer",
        "text": message_text,
    }
    history = [dict(item) for item in messages]
    messages.append(message)

    analysis, analysis_error = _analyze(
        message_text, history, dict(session.get("config") or {})
    )
    if analysis is not None:
        analysis["message_id"] = message["id"]
        _analyses(session).append(analysis)

    if analysis_error:
        return TurnOutcome(
            ok=False,
            message=message,
            error=analysis_error,
        )
    return TurnOutcome(ok=True, message=message, analysis=analysis)


def submit_agent_reply(
    session: MutableMapping[str, Any],
    text: str,
) -> TurnOutcome:
    """Validate and record one agent reply from the representative."""
    problem = _check_session(session)
    if problem:
        return TurnOutcome(ok=False, error=problem, invalid_session=True)

    error = validate_message(text, "Reply", MAX_MESSAGE_CHARS)
    if error:
        return TurnOutcome(ok=False, error=error)

    reply = str(text).strip()
    messages = _messages(session)

    if is_duplicate(messages, "agent", reply):
        return TurnOutcome(
            ok=False,
            error="That reply was already sent. Send a new reply.",
            duplicate=True,
        )

    message = {"id": next_message_id(session), "role": "agent", "text": reply}
    messages.append(message)

    tone = coaching.evaluate_agent_turn(reply)
    _tones(session).append(tone)
    return TurnOutcome(ok=True, message=message, tone=tone)


def message_count(
    session: MutableMapping[str, Any],
    role: str | None = None,
) -> int:
    """Count messages in a session, optionally filtered by role."""
    messages = session.get("messages") or []
    if role is None:
        return len(messages)
    return sum(str(item.get("role")) == role for item in messages)


def latest_analysis(session: MutableMapping[str, Any]) -> dict[str, Any] | None:
    analyses = session.get("analyses") or []
    return analyses[-1] if analyses else None


__all__ = [
    "MAX_MESSAGE_CHARS",
    "TurnOutcome",
    "is_duplicate",
    "latest_analysis",
    "message_count",
    "next_message_id",
    "normalize_text",
    "submit_agent_reply",
    "submit_customer_message",
    "valid_session_id",
]
