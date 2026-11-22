"""Bridge between Manual/Replay modes and the existing coaching pipeline.

Manual Mode and Replay Mode must produce the *same* structured analysis, so
both go through :func:`analyze_customer_turn` here.  The function reuses the
components the project already has instead of adding new agents:

* :mod:`backend.agents.intent_sentiment_agent` - intent, sentiment, emotion,
  frustration, escalation risk, sentiment trajectory/trend, conversation
  context and the structured Knowledge/Escalation/Coaching hand-offs.
* :mod:`utils.rag_stub` - knowledge retrieval over the ingested PDFs.
* :mod:`utils.pipeline_stub` - agent-reply tone/clarity scoring, and the
  rule-based analysis used **only** as a clearly-flagged fallback if the
  intent agent raises.  Agent output is never invented: a failed call is
  reported as ``source="pipeline_stub_fallback"`` with the error attached.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

from backend.agents.intent_sentiment_agent import analyze_message
from utils import pipeline_stub as fallback_pipeline
from utils import rag_stub

logger = logging.getLogger(__name__)

# Escalation risk (0-100) at which the console shows a prominent alert.
RISK_ALERT = 70

HANDOFF_SOURCE = "intent_sentiment_agent"
FALLBACK_SOURCE = "pipeline_stub_fallback"

_SENTIMENT_OPENERS = {
    "negative": "I'm sorry for the trouble this has caused, and thank you for "
    "sticking with us. ",
    "mixed": "Thanks for the details, and I'm sorry for the frustration. ",
    "neutral": "Thanks for the details. ",
    "positive": "I'm glad to hear that. ",
}

_PRIORITY_LABELS = {
    "p1_critical": "P1 - Critical",
    "p2_high": "P2 - High",
    "p3_medium": "P3 - Medium",
    "p4_low": "P4 - Low",
}


def _as_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(config or {})


def _humanise_intent(intent: str | None) -> str:
    if not intent:
        return "General inquiry"
    return intent.replace("_", " ").strip().capitalize()


def _text(message: Any) -> str:
    if not isinstance(message, Mapping):
        return ""
    return str(message.get("text") or "")


def _agent_history(history: Iterable[Any]) -> list[dict[str, Any]]:
    """Convert UI history dicts into the agent's history contract.

    Only customer turns are numbered; agent turns are included so the agent
    can see the full exchange, and are never classified as customer turns.
    """
    items: list[dict[str, Any]] = []
    turn = 0
    for message in history or []:
        role = str(message.get("role", "")) if isinstance(message, Mapping) else ""
        body = _text(message)
        if not body.strip():
            continue
        if role == "customer":
            turn += 1
            speaker = "customer"
        elif role == "agent":
            speaker = "agent"
        else:
            speaker = "system"
        items.append(
            {
                "speaker": speaker,
                "content": body,
                "turn_number": turn if speaker == "customer" else None,
            }
        )
    return items


def _knowledge_query(
    text: str,
    config: Mapping[str, Any],
    suggested_query: str | None = None,
) -> str:
    parts = [
        str(config.get("product") or "").strip(),
        str(config.get("scenario") or "").strip()[:180],
        text[:280],
        suggested_query or "",
    ]
    return " ".join(part for part in parts if part)


def retrieve_knowledge(query: str, k: int = 3) -> tuple[list[dict[str, Any]], str | None]:
    """Retrieve knowledge chunks, returning ``([], error)`` on failure."""
    try:
        return rag_stub.retrieve(query, k=k), None
    except Exception as exc:  # knowledge base problems must not break a turn
        logger.exception("Knowledge retrieval failed")
        return [], f"Knowledge retrieval failed: {exc}"


def _suggestion(
    *,
    sentiment: str,
    intent: str,
    guidance: str,
    focus_areas: list[str],
    chunks: list[dict[str, Any]],
) -> str:
    """Assemble a suggested response from the coaching hand-off + knowledge."""
    opener = _SENTIMENT_OPENERS.get(sentiment, _SENTIMENT_OPENERS["neutral"])
    parts = [
        opener,
        f"About your {_humanise_intent(intent).lower()}: {guidance}".strip(),
    ]

    if chunks:
        sources = []
        for chunk in chunks[:2]:
            source = str(chunk.get("source") or "the knowledge base")
            if source not in sources:
                sources.append(source)
        parts.append(
            "I'll walk you through the relevant guidance from "
            + " and ".join(sources)
            + "."
        )
    else:
        parts.append(
            "Let me share the exact next step and timeline before you go."
        )

    if focus_areas:
        parts.append(
            "Focus: " + ", ".join(area.replace("_", " ") for area in focus_areas) + "."
        )
    return " ".join(part for part in parts if part).strip()


def _empty_context() -> dict[str, Any]:
    return {
        "has_context": False,
        "customer_turns": 0,
        "dominant_intent": None,
        "recurring_issue": False,
        "unresolved_turns": 0,
        "average_prior_frustration": None,
        "prior_intents": [],
    }


def _base_analysis() -> dict[str, Any]:
    """Keys every analysis carries, so the console never needs guards."""
    return {
        "intent": "General inquiry",
        "intent_label": None,
        "intent_confidence": None,
        "sentiment": "Neutral",
        "emotion": "Neutral",
        "emotions": [],
        "frustration": 0,
        "frustration_score": 0.0,
        "frustration_level": "none",
        "sentiment_trend": "unknown",
        "risk": 0,
        "escalation_risk_score": 0.0,
        "escalation_priority": None,
        "escalation_priority_label": None,
        "requires_human_review": False,
        "risk_reason": "",
        "signals": [],
        "strategy": "",
        "coaching_focus": [],
        "coaching_guidance": "",
        "suggestion": "",
        "chunks": [],
        "knowledge_error": None,
        "conversation_context": _empty_context(),
        "sentiment_trajectory": [],
        "turn_number": None,
        "source": HANDOFF_SOURCE,
        "error": None,
    }


def _fallback_analysis(
    text: str,
    history: list[Any],
    config: dict[str, Any],
    error: Exception,
) -> dict[str, Any]:
    """Use the existing rule-based pipeline when the intent agent fails."""
    logger.exception("Intent agent failed; using rule-based fallback", exc_info=error)
    analysis = _base_analysis()
    analysis.update(fallback_pipeline.analyze_turn(text, history, config))
    analysis.update(
        {
            "intent_label": None,
            "frustration_level": (
                "severe"
                if analysis["frustration"] >= 75
                else "high"
                if analysis["frustration"] >= 60
                else "moderate"
                if analysis["frustration"] >= 40
                else "low"
                if analysis["frustration"] > 0
                else "none"
            ),
            "emotions": [str(analysis.get("emotion", "Neutral")).lower()],
            "source": FALLBACK_SOURCE,
            "error": str(error) or error.__class__.__name__,
            "signals": [analysis.get("risk_reason", "")],
        }
    )
    return analysis


def analyze_customer_turn(
    text: str,
    history: Iterable[Any] | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one customer message through the existing agent pipeline.

    Parameters
    ----------
    text:
        The customer message.  Empty input raises ``ValueError``; callers
        validate user input before reaching this point.
    history:
        Prior conversation messages (``{"role", "text"}`` mappings).  The
        new message must **not** be included.
    config:
        Session config carrying ``product`` and ``scenario`` context.

    Returns
    -------
    dict
        A JSON-serialisable analysis with the keys the coaching console
        renders, plus the escalation/coaching hand-off details.
    """
    message = (text or "").strip()
    if not message:
        raise ValueError("Customer message must not be empty.")

    prior = [item for item in (history or [])]
    cfg = _as_config(config)

    try:
        result = analyze_message(message, _agent_history(prior))
    except Exception as exc:  # never crash a live turn; fall back explicitly
        return _fallback_analysis(message, prior, cfg, exc)

    handoff = result.handoff
    sentiment = result.sentiment
    emotions = list(result.emotion or ["neutral"])
    primary_emotion = emotions[0] if emotions else "neutral"

    focus_areas: list[str] = []
    guidance = ""
    suggested_query = None
    priority = None
    signals: list[str] = []
    recommended_action = ""
    if handoff is not None:
        focus_areas = list(handoff.coaching.focus_areas)
        guidance = handoff.coaching.guidance
        suggested_query = handoff.knowledge.suggested_query
        priority = handoff.escalation.priority
        signals = list(handoff.escalation.signals)
        recommended_action = handoff.escalation.recommended_action

    chunks, knowledge_error = retrieve_knowledge(
        _knowledge_query(message, cfg, suggested_query)
    )

    risk = int(round(result.escalation_risk_score * 100))
    analysis = _base_analysis()
    analysis.update(
        {
            "intent": _humanise_intent(result.intent),
            "intent_label": result.intent,
            "intent_confidence": result.intent_confidence,
            "sentiment": sentiment.capitalize(),
            "emotion": primary_emotion.capitalize(),
            "emotions": [emotion.capitalize() for emotion in emotions],
            "frustration": int(round(result.frustration_score * 100)),
            "frustration_score": result.frustration_score,
            "frustration_level": result.frustration_level,
            "sentiment_trend": result.sentiment_trend,
            "risk": risk,
            "escalation_risk_score": result.escalation_risk_score,
            "escalation_priority": priority,
            "escalation_priority_label": _PRIORITY_LABELS.get(priority or ""),
            "requires_human_review": result.requires_human_review,
            "risk_reason": result.explanation,
            "signals": signals,
            "strategy": recommended_action
            or "Continue resolving; confirm the customer's understanding.",
            "coaching_focus": focus_areas,
            "coaching_guidance": guidance,
            "suggestion": _suggestion(
                sentiment=sentiment,
                intent=result.intent or "",
                guidance=guidance,
                focus_areas=focus_areas,
                chunks=chunks,
            ),
            "chunks": chunks,
            "knowledge_error": knowledge_error,
            "conversation_context": result.conversation_context.model_dump(
                mode="json"
            ),
            "sentiment_trajectory": [
                point.model_dump(mode="json")
                for point in result.sentiment_trajectory
            ],
            "turn_number": result.turn_number,
            "source": HANDOFF_SOURCE,
            "error": None,
        }
    )
    return analysis


def evaluate_agent_turn(text: str) -> dict[str, Any]:
    """Score an agent reply with the existing tone/clarity helper.

    Never invents a score: if the helper fails, ``score`` is ``None`` and the
    failure is surfaced in ``error`` so the console can say so.
    """
    body = (text or "").strip()
    try:
        tone = fallback_pipeline.evaluate_agent_reply(body)
    except Exception as exc:
        logger.exception("Agent reply evaluation failed")
        return {
            "score": None,
            "notes": ["Reply evaluation is unavailable for this message."],
            "error": str(exc),
        }
    return {**tone, "error": None}


def escalation_alert(analysis: Mapping[str, Any] | None) -> tuple[bool, str]:
    """Return ``(should_alert, message)`` for the latest analysis."""
    if not analysis:
        return False, ""

    risk = int(analysis.get("risk") or 0)
    requires_review = bool(analysis.get("requires_human_review"))
    if risk < RISK_ALERT and not requires_review:
        return False, ""

    priority = analysis.get("escalation_priority_label") or f"{risk}% risk"
    reason = str(analysis.get("risk_reason") or "Escalation signals detected.")
    return True, f"HIGH ESCALATION RISK - {priority} - {reason}"


__all__ = [
    "FALLBACK_SOURCE",
    "HANDOFF_SOURCE",
    "RISK_ALERT",
    "analyze_customer_turn",
    "escalation_alert",
    "evaluate_agent_turn",
    "retrieve_knowledge",
]
