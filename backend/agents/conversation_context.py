"""Conversation context and sentiment-tracking contracts.

These models make the Intent and Sentiment Analysis Agent's multi-turn
behaviour explicit and testable:

* :class:`SentimentTrajectoryPoint` records what one customer turn looked
  like (sentiment label, polarity, emotion indicators, frustration score),
  so sentiment changes can be inspected turn by turn instead of collapsed
  into a single trend label.
* :class:`ConversationContext` summarises the prior customer messages the
  agent used: which intents were seen, which one dominates, whether the
  current issue is recurring, and how frustrated the customer already was.

Neither model stores raw customer message text.  Downstream agents receive
labels, scores, and counts only, which keeps the payloads safe to log and
to persist alongside a session.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Emotion indicators the rule-based agent can report.  A single message may
# show several, so results carry a list rather than one label.
EmotionLabel = Literal[
    "frustration",
    "anger",
    "confusion",
    "disappointment",
    "satisfaction",
    "happiness",
    "urgency",
    "neutral",
]

SentimentLabel = Literal["positive", "neutral", "negative", "mixed"]
SentimentTrend = Literal["improving", "stable", "worsening", "unknown"]
FrustrationLevel = Literal["none", "low", "moderate", "high", "severe"]


class SentimentTrajectoryPoint(BaseModel):
    """Observed sentiment and frustration for one customer turn."""

    model_config = ConfigDict(extra="forbid")

    turn_number: int | None = Field(
        default=None,
        ge=1,
        description="1-indexed turn number, when the caller supplied one.",
    )
    sentiment: SentimentLabel = Field(
        description="Sentiment label for this turn.",
    )
    polarity: float = Field(
        ge=-1.0,
        le=1.0,
        description="Signed polarity in [-1, 1]; -1 is fully negative.",
    )
    emotions: list[EmotionLabel] = Field(
        default_factory=list,
        description="Emotion indicators detected in this turn.",
    )
    frustration_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Heuristic frustration estimate for this turn.",
    )


class ConversationContext(BaseModel):
    """Summary of the prior customer messages used for this analysis.

    An empty context (``has_context=False``) means the message was analysed
    as the first customer turn; every field is then zero/empty rather than
    ``None`` so consumers do not need optional chaining.
    """

    model_config = ConfigDict(extra="forbid")

    has_context: bool = Field(
        default=False,
        description="True when at least one prior customer message was used.",
    )
    customer_turns: int = Field(
        default=0,
        ge=0,
        description="Number of prior customer messages considered.",
    )
    window_start_turn: int | None = Field(
        default=None,
        ge=1,
        description="Earliest prior turn number in the analysis window.",
    )
    window_end_turn: int | None = Field(
        default=None,
        ge=1,
        description="Latest prior turn number in the analysis window.",
    )
    prior_intents: list[str] = Field(
        default_factory=list,
        description="Intent labels classified for prior customer turns, oldest first.",
    )
    dominant_intent: str | None = Field(
        default=None,
        description="Most frequent prior intent, or None when there is no history.",
    )
    unresolved_turns: int = Field(
        default=0,
        ge=0,
        description="Prior turns classified into the same intent as the current message.",
    )
    recurring_issue: bool = Field(
        default=False,
        description="True when the current intent already appeared in prior turns.",
    )
    average_prior_frustration: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Mean frustration score across prior customer turns.",
    )
    prior_emotion_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count of each emotion indicator across prior customer turns.",
    )


__all__ = [
    "ConversationContext",
    "EmotionLabel",
    "FrustrationLevel",
    "SentimentLabel",
    "SentimentTrajectoryPoint",
    "SentimentTrend",
]
