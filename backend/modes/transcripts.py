"""Transcript upload validation and parsing for Replay Mode.

Supported formats
-----------------
* ``.json`` - ``{"conversation_id": "...", "messages": [{"speaker": ...,
  "message"|"text"|"content": ...}]}`` or a bare list of message objects.
* ``.csv``  - a header row with a speaker column and a message column, for
  example ``speaker,message`` or ``role,text``.
* ``.txt``  - one message per line as ``Customer: ...`` / ``Agent: ...``;
  unlabelled lines continue the previous message.

Parsing is deliberately strict about things that would corrupt the replay
(speaker labels, malformed JSON/CSV, empty files) and forgiving about
cosmetic issues (blank messages are dropped with a warning, extra columns
are ignored).  Messages keep their original file order and receive stable
1-based ids so Replay Mode can address them by position.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# An uploaded transcript is text, not a document archive: 2 MB is a generous
# ceiling that also protects the Streamlit session from runaway files.
MAX_TRANSCRIPT_BYTES = 2 * 1024 * 1024
MIN_MESSAGES = 2
ALLOWED_EXTENSIONS = (".json", ".csv", ".txt")

SPEAKER_ALIASES: dict[str, str] = {
    "customer": "customer",
    "client": "customer",
    "user": "customer",
    "caller": "customer",
    "consumer": "customer",
    "agent": "agent",
    "support": "agent",
    "support agent": "agent",
    "representative": "agent",
    "rep": "agent",
    "advisor": "agent",
    "assistant": "agent",
    "staff": "agent",
    "operator": "agent",
}

# Alternative keys accepted for each field, checked case-insensitively.
_SPEAKER_KEYS = ("speaker", "role", "from", "author", "sender")
_MESSAGE_KEYS = ("message", "text", "content", "body", "utterance")
_CONVERSATION_KEYS = ("conversation_id", "conversation", "id", "session_id")

_TXT_LINE = re.compile(
    r"^\s*([A-Za-z][A-Za-z ]{1,24})\s*[:\-]\s*(.*)$"
)


class TranscriptError(ValueError):
    """Raised when an uploaded transcript cannot be replayed safely."""


@dataclass(frozen=True)
class TranscriptMessage:
    """One validated transcript message."""

    index: int
    role: str
    text: str

    @property
    def id(self) -> str:
        return f"msg-{self.index:04d}"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "role": self.role, "text": self.text}


@dataclass(frozen=True)
class Transcript:
    """A parsed, validated transcript ready for preview and replay."""

    conversation_id: str
    source_format: str
    filename: str
    messages: tuple[TranscriptMessage, ...]
    warnings: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return len(self.messages)

    @property
    def customer_count(self) -> int:
        return sum(message.role == "customer" for message in self.messages)

    def script(self) -> list[dict[str, str]]:
        """Return the ``[{"role", "text"}]`` script stored in session config."""
        return [
            {"id": message.id, "role": message.role, "text": message.text}
            for message in self.messages
        ]

    def preview_rows(self) -> list[dict[str, Any]]:
        """Rows for the preview table shown before replay starts."""
        return [
            {
                "#": message.index,
                "Speaker": message.role.title(),
                "Message": message.text,
            }
            for message in self.messages
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "source_format": self.source_format,
            "filename": self.filename,
            "messages": [message.to_dict() for message in self.messages],
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_speaker(raw: Any) -> str | None:
    """Map a raw speaker label onto ``"customer"`` / ``"agent"``.

    Returns ``None`` when the label is missing or unrecognised so callers
    can report a precise error instead of silently guessing.
    """
    if raw is None:
        return None
    if hasattr(raw, "value"):
        raw = raw.value
    label = re.sub(r"\s+", " ", str(raw)).strip().lower()
    return SPEAKER_ALIASES.get(label)


def detect_format(filename: str) -> str:
    """Return the lowercase extension without the dot.

    Raises
    ------
    TranscriptError
        When the file has no supported extension.
    """
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise TranscriptError(
            "Unsupported transcript file type. Upload a .json, .csv or .txt file."
        )
    return suffix.lstrip(".")


def _decode(raw: bytes | str) -> str:
    if isinstance(raw, str):
        return raw
    if not raw:
        raise TranscriptError("The transcript file is empty.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _pick(mapping: dict[str, Any], keys: Iterable[str]) -> Any:
    """Return the first present value for any of ``keys`` (case-insensitive)."""
    lowered = {
        str(key).strip().lower(): value
        for key, value in mapping.items()
        if isinstance(key, str)
    }
    for key in keys:
        if key in lowered:
            return lowered[key]
    return None


def _conversation_id(mapping: dict[str, Any] | None, fallback: str) -> str:
    if isinstance(mapping, dict):
        value = _pick(mapping, _CONVERSATION_KEYS)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()[:128]
    return fallback


# ---------------------------------------------------------------------------
# Format-specific parsers
# ---------------------------------------------------------------------------


def _parse_json(text: str, filename: str) -> tuple[str, list[tuple[Any, Any]], list[str]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TranscriptError(
            f"The JSON transcript is not valid JSON (line {exc.lineno}, "
            f"column {exc.colno})."
        ) from exc

    warnings: list[str] = []

    if isinstance(payload, dict):
        raw_messages = (
            payload.get("messages")
            or payload.get("conversation")
            or payload.get("turns")
        )
        conversation_id = _conversation_id(payload, Path(filename).stem)
    elif isinstance(payload, list):
        raw_messages = payload
        conversation_id = Path(filename).stem
    else:
        raise TranscriptError(
            "The JSON transcript must be an object with a 'messages' list "
            "or a list of messages."
        )

    if not isinstance(raw_messages, list):
        raise TranscriptError(
            "The JSON transcript has no 'messages' list to replay."
        )

    extracted: list[tuple[Any, Any]] = []
    for position, item in enumerate(raw_messages, 1):
        if not isinstance(item, dict):
            raise TranscriptError(
                f"JSON message {position} must be an object with a speaker "
                "and a message."
            )
        speaker = _pick(item, _SPEAKER_KEYS)
        body = _pick(item, _MESSAGE_KEYS)
        if speaker is None:
            raise TranscriptError(
                f"JSON message {position} is missing a speaker label "
                "('speaker' or 'role')."
            )
        if body is None:
            raise TranscriptError(
                f"JSON message {position} is missing its message text "
                "('message', 'text' or 'content')."
            )
        extracted.append((speaker, body))

    return conversation_id, extracted, warnings


def _parse_csv(text: str, filename: str) -> tuple[str, list[tuple[Any, Any]], list[str]]:
    warnings: list[str] = []
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]

    if not rows:
        raise TranscriptError("The CSV transcript is empty.")

    header = [cell.strip().lower() for cell in rows[0]]
    speaker_column = next(
        (header.index(key) for key in _SPEAKER_KEYS if key in header), None
    )
    message_column = next(
        (header.index(key) for key in _MESSAGE_KEYS if key in header), None
    )

    if speaker_column is None or message_column is None:
        raise TranscriptError(
            "The CSV transcript needs a header row with a speaker column "
            "('speaker' or 'role') and a message column ('message', 'text' "
            "or 'content')."
        )

    extracted: list[tuple[Any, Any]] = []
    for line_number, row in enumerate(rows[1:], 2):
        if len(row) <= max(speaker_column, message_column):
            raise TranscriptError(
                f"CSV row {line_number} has too few columns "
                f"({len(row)}); expected speaker and message."
            )
        extracted.append((row[speaker_column], row[message_column]))

    return Path(filename).stem, extracted, warnings


def _parse_txt(text: str, filename: str) -> tuple[str, list[tuple[Any, Any]], list[str]]:
    warnings: list[str] = []
    extracted: list[list[str]] = []

    for line in text.splitlines():
        if not line.strip():
            continue

        match = _TXT_LINE.match(line)
        role = normalize_speaker(match.group(1)) if match else None

        if match and role:
            extracted.append([role, match.group(2).strip()])
        elif match and not role:
            # Looks like "Name: text" but the speaker is not a customer or
            # agent; keep it only as a continuation of the previous message.
            if extracted:
                extracted[-1][1] = f"{extracted[-1][1]} {line.strip()}".strip()
                warnings.append(
                    f"Unrecognised speaker '{match.group(1).strip()}' treated "
                    "as a continuation line."
                )
            else:
                raise TranscriptError(
                    f"The first line has an unrecognised speaker "
                    f"('{match.group(1).strip()}'). Use 'Customer:' or "
                    "'Agent:'."
                )
        elif extracted:
            extracted[-1][1] = f"{extracted[-1][1]} {line.strip()}".strip()
        else:
            raise TranscriptError(
                "The TXT transcript must start with a speaker label, "
                "for example 'Customer: my order has not arrived'."
            )

    conversation_id = Path(filename).stem or "replay_txt"
    return conversation_id, [(role, body) for role, body in extracted], warnings


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def build_transcript(
    *,
    filename: str,
    source_format: str,
    conversation_id: str,
    raw_messages: Iterable[tuple[Any, Any]],
    warnings: Iterable[str] = (),
) -> Transcript:
    """Validate extracted messages and build a :class:`Transcript`."""
    messages: list[TranscriptMessage] = []
    collected_warnings = list(warnings)

    for position, (speaker_raw, body_raw) in enumerate(raw_messages, 1):
        role = normalize_speaker(speaker_raw)
        if role is None:
            raise TranscriptError(
                f"Message {position} has no recognisable speaker "
                f"('{speaker_raw}'). Use 'customer' or 'agent'."
            )

        if body_raw is None:
            body = ""
        elif isinstance(body_raw, str):
            body = body_raw
        else:
            body = str(body_raw)
        body = re.sub(r"\s+", " ", body).strip()

        if not body:
            collected_warnings.append(
                f"Message {position} was empty and has been skipped."
            )
            continue

        messages.append(
            TranscriptMessage(index=len(messages) + 1, role=role, text=body)
        )

    if not messages:
        raise TranscriptError(
            "The transcript contains no readable messages."
        )
    if len(messages) < MIN_MESSAGES:
        raise TranscriptError(
            f"The transcript needs at least {MIN_MESSAGES} messages to replay "
            f"(found {len(messages)})."
        )
    if not any(message.role == "customer" for message in messages):
        raise TranscriptError(
            "The transcript has no customer messages, so there is nothing to "
            "analyse during replay."
        )

    return Transcript(
        conversation_id=conversation_id or "replay_upload",
        source_format=source_format,
        filename=filename,
        messages=tuple(messages),
        warnings=tuple(collected_warnings),
    )


def parse_transcript_text(
    text: str | bytes,
    *,
    filename: str = "transcript.txt",
) -> Transcript:
    """Parse transcript content in the format implied by ``filename``.

    Raises
    ------
    TranscriptError
        For unsupported types, oversized or empty files, malformed content,
        missing speakers, or transcripts with fewer than two messages.
    """
    source_format = detect_format(filename)
    decoded = _decode(text)

    if not decoded.strip():
        raise TranscriptError("The transcript file is empty.")

    if source_format == "json":
        conversation_id, raw_messages, warnings = _parse_json(decoded, filename)
    elif source_format == "csv":
        conversation_id, raw_messages, warnings = _parse_csv(decoded, filename)
    else:
        conversation_id, raw_messages, warnings = _parse_txt(decoded, filename)

    return build_transcript(
        filename=filename,
        source_format=source_format,
        conversation_id=conversation_id,
        raw_messages=raw_messages,
        warnings=warnings,
    )


def parse_transcript_bytes(filename: str, raw: bytes | str) -> Transcript:
    """Validate size/type, then parse an uploaded transcript.

    This is the entry point used by the Streamlit uploader.
    """
    source_format = detect_format(filename)

    size = len(raw.encode("utf-8")) if isinstance(raw, str) else len(raw)
    if size == 0:
        raise TranscriptError("The transcript file is empty.")
    if size > MAX_TRANSCRIPT_BYTES:
        raise TranscriptError(
            "The transcript file is too large "
            f"({size // 1024} KB). The limit is "
            f"{MAX_TRANSCRIPT_BYTES // (1024 * 1024)} MB."
        )

    return parse_transcript_text(raw, filename=filename)


__all__ = [
    "ALLOWED_EXTENSIONS",
    "MAX_TRANSCRIPT_BYTES",
    "MIN_MESSAGES",
    "SPEAKER_ALIASES",
    "Transcript",
    "TranscriptError",
    "TranscriptMessage",
    "build_transcript",
    "detect_format",
    "normalize_speaker",
    "parse_transcript_bytes",
    "parse_transcript_text",
]
