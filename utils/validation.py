
"""Validate user input and return clear, plain-English error messages."""

import re


MODES = ("Simulator", "Manual", "Replay")


def validate_setup(mode, product, scenario, replay_script):
    errors = []

    if mode not in MODES:
        errors.append("Please select an interaction mode.")

    if len((product or "").strip()) < 3:
        errors.append(
            "Product context is required (at least 3 characters)."
        )

    scenario = scenario or ""

    if len(scenario.strip()) < 10:
        errors.append(
            "Please describe the customer scenario in at least 10 characters."
        )
    elif len(scenario) > 500:
        errors.append(
            "Scenario is too long — keep it under 500 characters."
        )

    if mode == "Replay" and len(replay_script or []) < 2:
        errors.append(
            "Replay mode needs a transcript with at least 2 messages "
            "(lines like 'Customer: ...' and 'Agent: ...')."
        )

    return errors


def validate_message(text, label="Message", max_len=1500):
    text = (text or "").strip()

    if not text:
        return f"{label} can't be empty."

    if len(text) > max_len:
        return f"{label} is too long (max {max_len} characters)."

    return None


def parse_transcript(raw: str):
    """Parse Customer/Agent transcript lines into role and text dictionaries."""
    msgs = []

    for line in (raw or "").splitlines():
        match = re.match(
            r"^\s*(customer|agent)\s*:\s*(.+)$",
            line,
            re.IGNORECASE,
        )

        if match:
            msgs.append({
                "role": match.group(1).lower(),
                "text": match.group(2).strip(),
            })
        elif msgs and line.strip():
            msgs[-1]["text"] += " " + line.strip()

    return msgs
