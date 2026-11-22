"""Session persistence utilities for JSON storage in data/sessions/.

Implements the flat Milestone 1 session schema and a tolerant loader
for migrating legacy session formats on read.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import SESSIONS_DIR

DIR = SESSIONS_DIR


def new_id() -> str:
    """Generate a clean, unique session identifier."""
    return f"sess-{uuid.uuid4().hex[:8]}"


def _normalize_session_dict(raw: dict[str, Any], sid: str) -> dict[str, Any]:
    """Tolerantly convert legacy session formats into the flat Milestone 1 schema."""
    # 1. Mode normalization (Simulator | Manual | Replay)
    mode_raw = str(raw.get("mode") or raw.get("config", {}).get("mode") or "Simulator")
    mode_norm = mode_raw.capitalize()
    if mode_norm not in ("Simulator", "Manual", "Replay"):
        mode_norm = "Simulator"

    # 2. Product context extraction (plain string)
    prod = raw.get("product")
    if not prod:
        prod_ctx = raw.get("product_context")
        if isinstance(prod_ctx, dict):
            prod = prod_ctx.get("product")
        elif prod_ctx:
            prod = str(prod_ctx)
        else:
            prod = raw.get("config", {}).get("product", "Acme Online Store")
    prod = str(prod or "Acme Online Store").strip()

    # 3. Scenario extraction
    scenario = raw.get("scenario") or raw.get("config", {}).get("scenario") or ""

    # 4. Persona (Simulator only)
    if mode_norm == "Simulator":
        persona = (
            raw.get("persona")
            or raw.get("customer_persona")
            or raw.get("metadata", {}).get("persona")
            or "Calm"
        )
    else:
        persona = None

    # 5. Max turns (Simulator only)
    if mode_norm == "Simulator":
        max_turns = (
            raw.get("max_turns")
            or raw.get("metadata", {}).get("max_turns")
            or 5
        )
        try:
            max_turns = int(max_turns)
        except (ValueError, TypeError):
            max_turns = 5
    else:
        max_turns = None

    # 6. Replay transcript (Replay only)
    if mode_norm == "Replay":
        replay_tx = (
            raw.get("replay_transcript")
            or raw.get("metadata", {}).get("replay_script")
            or []
        )
    else:
        replay_tx = None

    # 7. Knowledge base documents snapshot
    kb_docs = raw.get("kb_documents")
    if kb_docs is None:
        kb_docs = []

    # 8. Status (Milestone 1 is always 'configured')
    status = "configured"

    # 9. Created timestamp (one timestamp, local ISO)
    created_at = raw.get("created_at") or raw.get("saved_at")
    if not created_at:
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    else:
        # Convert UTC or string timestamp to consistent format if possible
        try:
            if isinstance(created_at, str) and "T" in created_at:
                dt = datetime.fromisoformat(created_at)
                created_at = dt.astimezone().isoformat(timespec="seconds")
        except Exception:
            pass

    return {
        "session_id": sid,
        "mode": mode_norm,
        "product": prod,
        "scenario": scenario,
        "persona": persona,
        "max_turns": max_turns,
        "replay_transcript": replay_tx,
        "kb_documents": kb_docs,
        "status": status,
        "created_at": str(created_at),
    }


def save(session_data: Any) -> str | None:
    """Save session data to data/sessions/<id>.json in the flat schema."""
    DIR.mkdir(parents=True, exist_ok=True)

    if hasattr(session_data, "to_dict") and hasattr(session_data, "session_id"):
        sid = session_data.session_id
        data = session_data.to_dict()
    elif isinstance(session_data, dict):
        sid = session_data.get("session_id") or session_data.get("sid")
        data = dict(session_data)
    else:
        sid = getattr(session_data, "session_id", None) or getattr(session_data, "sid", None)
        if not sid and hasattr(session_data, "get"):
            sid = session_data.get("session_id") or session_data.get("sid")
        if hasattr(session_data, "to_dict"):
            data = session_data.to_dict()
        else:
            data = {"session_id": sid}

    if not sid:
        return None

    # Enforce flat schema normalization before saving
    normalized = _normalize_session_dict(data, sid)

    file_path = DIR / f"{sid}.json"
    file_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return sid


def load(sid: str | None) -> dict[str, Any] | None:
    """Load and migrate session JSON by session_id."""
    if not sid:
        return None

    clean_sid = str(sid).strip()
    session_file = DIR / f"{clean_sid}.json"
    if not session_file.exists():
        return None

    try:
        raw_data = json.loads(session_file.read_text(encoding="utf-8"))
        # Tolerantly normalize to flat schema
        return _normalize_session_dict(raw_data, clean_sid)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def count() -> int:
    """Return total number of saved session JSON files."""
    if not DIR.exists():
        return 0
    return len(list(DIR.glob("*.json")))


def list_sessions(limit: int | None = None) -> list[tuple[str, str, str, str, str | None, int | None]]:
    """Return list of (session_id, created_at, mode, product, persona, max_turns) newest first."""
    if not DIR.exists():
        return []

    rows = []
    session_files = sorted(
        DIR.glob("*.json"),
        key=lambda file: file.stat().st_mtime,
        reverse=True,
    )

    if limit is not None:
        session_files = session_files[:limit]

    for session_file in session_files:
        try:
            raw = json.loads(session_file.read_text(encoding="utf-8"))
            data = _normalize_session_dict(raw, session_file.stem)
            rows.append((
                data["session_id"],
                data["created_at"],
                data["mode"],
                data["product"],
                data["persona"],
                data["max_turns"],
            ))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue

    return rows


def delete_session(sid: str | None) -> bool:
    """Safely delete one saved session JSON file."""
    if not sid:
        return False

    sessions_dir = DIR.resolve()
    session_file = (sessions_dir / f"{sid}.json").resolve()

    try:
        session_file.relative_to(sessions_dir)
        if session_file.is_file():
            session_file.unlink()
            return True
        return False
    except (OSError, ValueError):
        return False


def delete_all_sessions() -> int:
    """Safely delete all saved session JSON files in data/sessions/."""
    if not DIR.exists():
        return 0
    removed = 0
    for file_path in list(DIR.glob("*.json")):
        try:
            file_path.unlink()
            removed += 1
        except OSError:
            pass
    return removed
