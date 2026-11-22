"""Replay Mode position management.

Replay is modelled as a **position** in the transcript rather than an
append-only log: the conversation shown is always ``transcript[:position]``,
and analyses for customer messages are cached by transcript index.

That design gives the guarantees Replay Mode needs:

* stepping backwards truncates the visible conversation instead of adding
  turns, so no duplicate turns or duplicate analysis records are created;
* stepping forwards again reuses the cached analysis, so results are stable
  and no agent calls are repeated for messages already analysed;
* agent messages are recorded in the conversation history and scored with
  the coaching helper, but are never classified as customer messages.

The module is UI-free: the Streamlit console passes ``session_state`` as the
session mapping, tests pass a plain dict.
"""

from __future__ import annotations

from typing import Any, MutableMapping

from backend.modes import coaching

REPLAY_STATUSES = ("idle", "playing", "paused", "finished")
SCRIPT_KEY = "replay_script"


def _script(session: MutableMapping[str, Any]) -> list[dict[str, Any]]:
    config = session.get("config") or {}
    script = config.get(SCRIPT_KEY) if isinstance(config, dict) else None
    if not isinstance(script, list):
        return []
    return [item for item in script if isinstance(item, dict)]


def _role(item: dict[str, Any], position: int) -> str:
    role = str(item.get("role") or "").strip().lower()
    if role not in ("customer", "agent"):
        raise ValueError(
            f"Replay transcript message {position} has an unsupported "
            f"speaker ({item.get('role')!r})."
        )
    return role


def _text(item: dict[str, Any]) -> str:
    return str(item.get("text") or "").strip()


def total(session: MutableMapping[str, Any]) -> int:
    return len(_script(session))


def _clamp(index: Any, maximum: int) -> int:
    try:
        value = int(index)
    except (TypeError, ValueError):
        value = 0
    return max(0, min(value, maximum))


def init_state(
    session: MutableMapping[str, Any],
    *,
    reset: bool = False,
) -> dict[str, Any]:
    """Make sure the replay keys exist; optionally reset the replay.

    ``reset=True`` is used when a new transcript is loaded: cached analyses
    belong to the old transcript and must not leak into the new one.
    """
    if not isinstance(session.get("replay_analyses"), dict):
        session["replay_analyses"] = {}
    if not isinstance(session.get("replay_tones"), dict):
        session["replay_tones"] = {}

    if reset:
        session["replay_analyses"] = {}
        session["replay_tones"] = {}
        session["replay_idx"] = 0
        session["replay_status"] = "idle"
        session["messages"] = []
        session["analyses"] = []
        session["tone"] = []

    position = _clamp(session.get("replay_idx", 0), total(session))
    session["replay_idx"] = position
    status = session.get("replay_status")
    if status not in REPLAY_STATUSES:
        status = "finished" if position >= total(session) and total(session) else "idle"
        session["replay_status"] = status
    return state(session)


def _rebuild(session: MutableMapping[str, Any], index: int) -> None:
    """Rebuild the visible conversation for ``transcript[:index]``."""
    script = _script(session)
    index = _clamp(index, len(script))

    cache = session.get("replay_analyses")
    if not isinstance(cache, dict):
        cache = {}
        session["replay_analyses"] = cache
    tone_cache = session.get("replay_tones")
    if not isinstance(tone_cache, dict):
        tone_cache = {}
        session["replay_tones"] = tone_cache

    config = dict(session.get("config") or {})
    messages: list[dict[str, Any]] = []
    analyses: list[dict[str, Any]] = []
    tones: list[dict[str, Any]] = []

    for position in range(index):
        item = script[position]
        role = _role(item, position + 1)
        text = _text(item)
        message = {
            "id": str(item.get("id") or f"msg-{position + 1:04d}"),
            "role": role,
            "text": text,
        }
        messages.append(message)
        key = str(position)

        if role == "customer":
            analysis = cache.get(key)
            if not isinstance(analysis, dict):
                analysis = coaching.analyze_customer_turn(
                    text, messages[:-1], config
                )
                cache[key] = analysis
            analyses.append({**analysis, "message_id": message["id"]})
        else:
            tone = tone_cache.get(key)
            if not isinstance(tone, dict):
                tone = coaching.evaluate_agent_turn(text)
                tone_cache[key] = tone
            tones.append(tone)

    session["messages"] = messages
    session["analyses"] = analyses
    session["tone"] = tones
    session["replay_idx"] = index
    if len(script) and index >= len(script):
        session["replay_status"] = "finished"


def state(session: MutableMapping[str, Any]) -> dict[str, Any]:
    """Describe the replay: position, total, status and current message."""
    script = _script(session)
    count = len(script)
    position = _clamp(session.get("replay_idx", 0), count)
    status = session.get("replay_status")
    if status not in REPLAY_STATUSES:
        status = "idle"

    current = None
    if position < count:
        item = script[position]
        current = {
            "index": position + 1,
            "id": str(item.get("id") or f"msg-{position + 1:04d}"),
            "role": _role(item, position + 1),
            "text": _text(item),
        }

    return {
        "position": position,
        "total": count,
        "status": status,
        "progress": (position / count) if count else 0.0,
        "current": current,
        "finished": count > 0 and position >= count,
        "has_script": count > 0,
    }


def go_to(session: MutableMapping[str, Any], index: int) -> dict[str, Any]:
    """Move the replay to an absolute transcript position."""
    _rebuild(session, index)
    return state(session)


def next_message(session: MutableMapping[str, Any]) -> dict[str, Any]:
    """Advance one message; the replay finishes at the end of the transcript."""
    current = state(session)
    if not current["has_script"] or current["finished"]:
        return current

    _rebuild(session, current["position"] + 1)
    if session.get("replay_status") != "finished":
        session["replay_status"] = (
            "playing" if current["status"] == "playing" else "paused"
        )
    return state(session)


def previous_message(session: MutableMapping[str, Any]) -> dict[str, Any]:
    """Step back one message without duplicating turns or analyses."""
    current = state(session)
    _rebuild(session, current["position"] - 1)
    session["replay_status"] = "paused"
    return state(session)


def restart(session: MutableMapping[str, Any]) -> dict[str, Any]:
    """Return to the beginning of the transcript and clear the visible chat.

    Cached per-index analyses are kept: replaying forwards reuses them
    instead of re-running the agents, which keeps results deterministic.
    """
    _rebuild(session, 0)
    session["replay_status"] = "idle"
    return state(session)


def start(session: MutableMapping[str, Any]) -> dict[str, Any]:
    """Start (or resume) playback from the current position."""
    current = state(session)
    if not current["has_script"]:
        return current
    if current["finished"]:
        restart(session)
        current = state(session)

    session["replay_status"] = "playing"
    _rebuild(session, current["position"])
    session["replay_status"] = "playing"
    return state(session)


def pause(session: MutableMapping[str, Any]) -> dict[str, Any]:
    if session.get("replay_status") == "playing":
        session["replay_status"] = "paused"
    return state(session)


def resume(session: MutableMapping[str, Any]) -> dict[str, Any]:
    current = state(session)
    if current["has_script"] and not current["finished"]:
        session["replay_status"] = "playing"
    return state(session)


def auto_advance(session: MutableMapping[str, Any]) -> dict[str, Any]:
    """Advance one message while playing; used by the auto-play control."""
    current = state(session)
    if current["status"] != "playing" or current["finished"]:
        if current["finished"]:
            session["replay_status"] = "finished"
        return state(session)
    return next_message(session)


def current_analysis(session: MutableMapping[str, Any]) -> dict[str, Any] | None:
    analyses = session.get("analyses") or []
    return analyses[-1] if analyses else None


__all__ = [
    "REPLAY_STATUSES",
    "auto_advance",
    "current_analysis",
    "go_to",
    "init_state",
    "next_message",
    "pause",
    "previous_message",
    "restart",
    "resume",
    "start",
    "state",
    "total",
]
