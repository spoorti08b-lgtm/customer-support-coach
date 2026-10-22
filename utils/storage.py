"""Session persistence: sessions are saved as JSON so a browser refresh can reload them.
The session id lives in the URL (?sid=...), so refreshing the page restores the session."""
import json
import time
import uuid
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "data" / "sessions"
DEFAULTS = {"view": "setup", "config": {}, "messages": [], "analyses": [], "tone": [], "replay_idx": 0}


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def save(state) -> None:
    sid = state.get("sid")
    if not sid:
        return
    DIR.mkdir(parents=True, exist_ok=True)
    data = {k: state.get(k, v) for k, v in DEFAULTS.items()}
    data["saved_at"] = time.strftime("%Y-%m-%d %H:%M")
    (DIR / f"{sid}.json").write_text(json.dumps(data, indent=2))


def load(sid):
    if not sid or not str(sid).isalnum():
        return None
    p = DIR / f"{sid}.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return None
    return {k: data.get(k, v) for k, v in DEFAULTS.items()}


def list_sessions(limit=8):
    if not DIR.exists():
        return []
    rows = []
    for p in sorted(DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            d = json.loads(p.read_text())
            rows.append((p.stem, d.get("saved_at", ""), d.get("config", {}).get("mode", "?")))
        except json.JSONDecodeError:
            continue
    return rows

from pathlib import Path

def delete_session(sid):
    """Delete one saved session JSON file safely."""
    # Allow only simple session IDs to prevent path traversal.
    if not sid or not sid.replace("-", "").replace("_", "").isalnum():
        return False

    sessions_dir = Path(__file__).resolve().parent.parent / "data" / "sessions"
    session_file = sessions_dir / f"{sid}.json"

    try:
        session_file.resolve().relative_to(sessions_dir.resolve())

        if not session_file.is_file():
            return False

        session_file.unlink()
        return True

    except (OSError, ValueError):
        return False
