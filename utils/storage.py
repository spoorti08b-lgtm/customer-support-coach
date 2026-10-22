
"""Save sessions as JSON so they can be reloaded after a browser refresh."""

import json
import time
import uuid
from pathlib import Path


DIR = Path(__file__).resolve().parent.parent / "data" / "sessions"

DEFAULTS = {
    "view": "setup",
    "config": {},
    "messages": [],
    "analyses": [],
    "tone": [],
    "replay_idx": 0,
}


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def save(state) -> None:
    sid = state.get("sid")
    if not sid:
        return

    DIR.mkdir(parents=True, exist_ok=True)
    data = {key: state.get(key, value) for key, value in DEFAULTS.items()}
    data["saved_at"] = time.strftime("%Y-%m-%d %H:%M")

    (DIR / f"{sid}.json").write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def load(sid):
    if not sid or not str(sid).isalnum():
        return None

    session_file = DIR / f"{sid}.json"
    if not session_file.exists():
        return None

    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None

    return {key: data.get(key, value) for key, value in DEFAULTS.items()}


def list_sessions(limit=8):
    if not DIR.exists():
        return []

    rows = []
    session_files = sorted(
        DIR.glob("*.json"),
        key=lambda file: file.stat().st_mtime,
        reverse=True,
    )

    for session_file in session_files[:limit]:
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            config = data.get("config", {})
            rows.append(
                (
                    session_file.stem,
                    data.get("saved_at", ""),
                    config.get("mode", "?"),
                )
            )
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue

    return rows


def delete_session(sid):
    """Safely delete one saved session."""
    if not sid or not sid.replace("-", "").replace("_", "").isalnum():
        return False

    sessions_dir = DIR.resolve()
    session_file = sessions_dir / f"{sid}.json"

    try:
        session_file.resolve().relative_to(sessions_dir)

        if not session_file.is_file():
            return False

        session_file.unlink()
        return True

    except (OSError, ValueError):
        return False
