"""Structured hand-off payloads for downstream Milestone 2 agents.

The Intent and Sentiment Analysis Agent is the entry point of the workflow,
so its output is what the Knowledge, Escalation, and Coaching agents
consume.  Rather than have each downstream agent re-derive routing decisions
from a flat sentiment blob, the analysis result carries one typed payload
per consumer:

* :class:`KnowledgeHandoff` - what to retrieve for, and how much context the
  customer has already given.
* :class:`EscalationHandoff` - whether a human is needed, at what priority,
  and which signals justify that decision.
* :class:`CoachingHandoff` - which coaching focus areas the agent turn
  should target.

Payloads deliberately contain labels, scores, and counts only.  Raw customer
message text is never copied into a hand-off; the orchestrator already holds
the message and can pass it to the Knowledge agent alongside this contract.
"""

from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from backend.agents.conversation_context import (
    EmotionLabel,
    FrustrationLevel,
    SentimentLabel,
    SentimentTrend,
)

EscalationPriority = Literal["p1_critical", "p2_high", "p3_medium", "p4_low"]


class KnowledgeHandoff(BaseModel):
    """Retrieval brief for the Knowledge Recommendation Agent."""

    model_config = ConfigDict(extra="forbid")

    intent: str = Field(min_length=1, description="Detected customer intent.")
    intent_confidence: float = Field(
        ge=0.0, le=1.0, description="Heuristic intent confidence."
    )
    suggested_query: str = Field(
        min_length=1,
        max_length=200,
        description="Content-free query hint derived from the intent label.",
    )
    sentiment: SentimentLabel = Field(description="Current message sentiment.")
    emotions: list[EmotionLabel] = Field(
        default_factory=list,
        description="Emotion indicators for the current message.",
    )
    turn_number: int = Field(ge=1, description="Current 1-indexed turn.")
    customer_turns_of_context: int = Field(
        default=0,
        ge=0,
        description="Prior customer turns available for context-aware retrieval.",
    )
    recurring_issue: bool = Field(
        default=False,
        description="True when the customer has raised this intent before.",
    )


class EscalationHandoff(BaseModel):
    """Routing brief for the Escalation Agent."""

    model_config = ConfigDict(extra="forbid")

    priority: EscalationPriority = Field(
        description="Recommended handling priority.",
    )
    requires_human_review: bool = Field(
        description="True when the analysis crossed the human-review threshold.",
    )
    escalation_risk_score: float = Field(
        ge=0.0, le=1.0, description="Heuristic escalation-risk score."
    )
    frustration_level: FrustrationLevel = Field(
        description="Banded frustration level for this turn."
    )
    sentiment_trend: SentimentTrend = Field(
        description="Direction of sentiment across customer turns."
    )
    signals: list[str] = Field(
        min_length=1,
        description="Machine-readable risk signals behind the decision.",
    )
    recommended_action: str = Field(
        min_length=1,
        max_length=300,
        description="Short routing recommendation for the Escalation Agent.",
    )


class CoachingHandoff(BaseModel):
    """Coaching brief for the Coaching Agent."""

    model_config = ConfigDict(extra="forbid")

    focus_areas: list[str] = Field(
        min_length=1,
        description="Coaching areas the agent turn should target, most relevant first.",
    )
    sentiment: SentimentLabel = Field(description="Current message sentiment.")
    sentiment_trend: SentimentTrend = Field(
        description="Direction of sentiment across customer turns."
    )
    frustration_level: FrustrationLevel = Field(
        description="Banded frustration level for this turn."
    )
    dominant_emotion: EmotionLabel = Field(
        description="Primary emotion to acknowledge, or 'neutral'."
    )
    guidance: str = Field(
        min_length=1,
        max_length=300,
        description="Short coaching guidance derived from the detected signals.",
    )


class AgentHandoff(BaseModel):
    """All downstream hand-off payloads produced for one turn."""

    model_config = ConfigDict(extra="forbid")

    knowledge: KnowledgeHandoff
    escalation: EscalationHandoff
    coaching: CoachingHandoff


# ---------------------------------------------------------------------------
# Derivation rules
# ---------------------------------------------------------------------------

# Emotion -> coaching focus area.  Ordering follows ``EMOTION_INDICATORS``
# declaration order, so the most specific signal leads the focus list.
_EMOTION_FOCUS: dict[str, str] = {
    "frustration": "empathy_and_ownership",
    "anger": "de_escalation",
    "confusion": "clarify_and_confirm",
    "disappointment": "expectation_management",
    "satisfaction": "reinforce_and_close",
    "happiness": "reinforce_and_close",
    "urgency": "time_commitment",
}

_FOCUS_GUIDANCE: dict[str, str] = {
    "empathy_and_ownership": (
        "Acknowledge the customer's frustration and take ownership before "
        "offering next steps."
    ),
    "de_escalation": (
        "Stay calm and non-defensive, acknowledge the anger, and focus on "
        "one concrete resolution path."
    ),
    "clarify_and_confirm": (
        "Explain the situation in plain language and confirm understanding "
        "before closing the turn."
    ),
    "expectation_management": (
        "Be explicit about what can be done now and when the customer will "
        "hear back."
    ),
    "reinforce_and_close": (
        "Reinforce the positive outcome, confirm nothing else is needed, "
        "and close warmly."
    ),
    "time_commitment": (
        "Give a specific timeframe and commit to the next update."
    ),
    "sentiment_recovery": (
        "Name the worsening experience, apologise for the journey, and "
        "restate the recovery plan."
    ),
    "context_continuity": (
        "Reference what the customer already told you instead of asking "
        "them to repeat it."
    ),
    "discovery_questions": (
        "Ask focused questions to uncover the underlying need before "
        "suggesting a fix."
    ),
}

_EMOTION_LABELS: frozenset[str] = frozenset(
    {
        "frustration",
        "anger",
        "confusion",
        "disappointment",
        "satisfaction",
        "happiness",
        "urgency",
        "neutral",
    }
)

_RECOMMENDED_ACTIONS: dict[str, str] = {
    "p1_critical": (
        "Route to a senior support specialist immediately and pause "
        "automated handling."
    ),
    "p2_high": "Assign a human agent and confirm ownership within this turn.",
    "p3_medium": (
        "Continue automated handling but monitor closely and give the "
        "customer a clear plan."
    ),
    "p4_low": "Continue standard handling; no escalation required.",
}


def escalation_priority(
    *,
    risk: float,
    frustration_level: FrustrationLevel,
    requires_human_review: bool,
    sentiment_trend: SentimentTrend = "unknown",
    critical_threshold: float = 0.80,
) -> EscalationPriority:
    """Map the analysis scores onto a handling priority.

    Critical takes precedence over the review flag so that a severe case is
    never queued as merely high.  A worsening trend alone is enough for
    medium priority, which keeps churn risk visible without paging a human.
    """
    if risk >= critical_threshold or frustration_level == "severe":
        return "p1_critical"
    if requires_human_review:
        return "p2_high"
    if frustration_level == "high" or sentiment_trend == "worsening":
        return "p3_medium"
    return "p4_low"


def suggested_knowledge_query(intent: str) -> str:
    """Build a retrieval hint from an intent label (never message content)."""
    readable = intent.replace("_", " ").strip() or "general"
    return f"{readable} customer support policy"[:200]


def coaching_focus_areas(
    emotions: list[str],
    sentiment_trend: SentimentTrend,
    recurring_issue: bool,
) -> list[str]:
    """Derive ordered, de-duplicated coaching focus areas."""
    focus: list[str] = []
    for emotion in emotions:
        area = _EMOTION_FOCUS.get(emotion)
        if area and area not in focus:
            focus.append(area)
    if sentiment_trend == "worsening" and "sentiment_recovery" not in focus:
        focus.append("sentiment_recovery")
    if recurring_issue and "context_continuity" not in focus:
        focus.append("context_continuity")
    return focus or ["discovery_questions"]


def coaching_guidance(
    focus_areas: list[str],
    frustration_level: FrustrationLevel,
    sentiment_trend: SentimentTrend,
) -> str:
    """Compose one short guidance sentence from the top focus areas."""
    primary = focus_areas[0]
    parts = [_FOCUS_GUIDANCE.get(primary, _FOCUS_GUIDANCE["discovery_questions"])]
    if frustration_level in {"high", "severe"}:
        parts.append("Keep the tone calm and concrete; avoid policy jargon.")
    if sentiment_trend == "worsening":
        parts.append("Acknowledge the deteriorating experience explicitly.")
    return " ".join(parts)[:300]


def build_handoff(
    *,
    intent: str,
    intent_confidence: float,
    sentiment: SentimentLabel,
    emotions: list[str],
    turn_number: int,
    sentiment_trend: SentimentTrend,
    frustration_level: FrustrationLevel,
    escalation_risk_score: float,
    requires_human_review: bool,
    recurring_issue: bool,
    customer_turns_of_context: int,
    signals: list[str],
    critical_threshold: float = 0.80,
) -> AgentHandoff:
    """Assemble all three downstream payloads from one analysis."""
    priority = escalation_priority(
        risk=escalation_risk_score,
        frustration_level=frustration_level,
        requires_human_review=requires_human_review,
        sentiment_trend=sentiment_trend,
        critical_threshold=critical_threshold,
    )

    # Typed fields expect the literal emotion set; unknown custom labels are
    # dropped rather than rejected.
    typed_emotions: list[EmotionLabel] = [
        cast(EmotionLabel, emotion)
        for emotion in emotions
        if emotion in _EMOTION_LABELS
    ] or ["neutral"]

    focus_areas = coaching_focus_areas(emotions, sentiment_trend, recurring_issue)
    dominant_emotion: EmotionLabel = typed_emotions[0]

    return AgentHandoff(
        knowledge=KnowledgeHandoff(
            intent=intent,
            intent_confidence=intent_confidence,
            suggested_query=suggested_knowledge_query(intent),
            sentiment=sentiment,
            emotions=typed_emotions,
            turn_number=turn_number,
            customer_turns_of_context=customer_turns_of_context,
            recurring_issue=recurring_issue,
        ),
        escalation=EscalationHandoff(
            priority=priority,
            requires_human_review=requires_human_review,
            escalation_risk_score=escalation_risk_score,
            frustration_level=frustration_level,
            sentiment_trend=sentiment_trend,
            signals=signals or ["no_escalation_signals"],
            recommended_action=_RECOMMENDED_ACTIONS[priority],
        ),
        coaching=CoachingHandoff(
            focus_areas=focus_areas,
            sentiment=sentiment,
            sentiment_trend=sentiment_trend,
            frustration_level=frustration_level,
            dominant_emotion=dominant_emotion,
            guidance=coaching_guidance(
                focus_areas, frustration_level, sentiment_trend
            ),
        ),
    )


__all__ = [
    "AgentHandoff",
    "CoachingHandoff",
    "EscalationHandoff",
    "EscalationPriority",
    "KnowledgeHandoff",
    "build_handoff",
    "coaching_focus_areas",
    "coaching_guidance",
    "escalation_priority",
    "suggested_knowledge_query",
]
