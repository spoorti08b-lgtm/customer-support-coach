"""Validation utilities for session configuration, user inputs, and transcripts."""

from __future__ import annotations

import re
from typing import Any

MODES = ("Simulator", "Manual", "Replay")
PERSONAS = ("Calm", "Frustrated", "Angry", "Confused", "Impatient")


def validate_setup(
    mode: str,
    product: str,
    scenario: str,
    replay_script: list[dict[str, Any]] | None = None,
    kb_chunk_count: int | None = None,
) -> list[str]:
    """Validate session configuration parameters and return a list of error strings."""
    errors: list[str] = []

    if kb_chunk_count is not None and kb_chunk_count < 1:
        errors.append("Add documents.")

    product_clean = (product or "").strip()
    if not product_clean:
        errors.append("Add a product.")
    elif len(product_clean) < 3:
        errors.append("Product needs at least 3 characters.")
    elif len(product_clean) > 100:
        errors.append("Product needs at most 100 characters.")

    scenario_clean = (scenario or "").strip()
    if not scenario_clean:
        errors.append("Describe the problem.")
    elif len(scenario_clean) < 10:
        errors.append(f"Problem needs at least 10 characters ({len(scenario_clean)} now).")
    elif len(scenario_clean) > 500:
        errors.append("Problem needs at most 500 characters.")

    if mode not in MODES:
        errors.append("Please select a valid interaction mode (Simulator, Manual, Replay).")

    if mode == "Replay":
        if not replay_script or len(replay_script) < 2:
            errors.append(
                "Replay mode requires a transcript with at least 2 parsed messages."
            )

    return errors


def format_validation_hint(errors: list[str]) -> str:
    """Format validation errors into a single plain-language hint line.

    If multiple errors exist, joins the first two with ' . '.
    """
    if not errors:
        return ""
    clean = [e.rstrip(".") for e in errors[:2]]
    return " . ".join(clean) + "."


def validate_message(text: str, label: str = "Message", max_len: int = 1500) -> str | None:
    """Validate a conversation message string."""
    clean = (text or "").strip()
    if not clean:
        return f"{label} cannot be empty."
    if len(clean) > max_len:
        return f"{label} is too long (maximum {max_len} characters)."
    return None


def parse_transcript(raw: str) -> list[dict[str, str]]:
    """Parse transcript text into structured list of messages.
    
    Expects lines beginning with 'Customer:' or 'Agent:'.
    """
    msgs: list[dict[str, str]] = []

    for line in (raw or "").splitlines():
        match = re.match(r"^\s*(customer|agent)\s*:\s*(.+)$", line, re.IGNORECASE)
        if match:
            msgs.append({
                "role": match.group(1).lower(),
                "text": match.group(2).strip(),
            })
        elif msgs and line.strip():
            # Append continuation line to previous message
            msgs[-1]["text"] += " " + line.strip()

    return msgs
