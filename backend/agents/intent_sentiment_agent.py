"""Intent and Sentiment Analysis Agent.

Analyses a single customer-support message (optionally with conversation
history) and returns a structured result covering:

* intent classification with a heuristic confidence,
* sentiment (positive / neutral / negative / mixed),
* emotion indicators (a message may show several),
* a frustration score in [0, 1],
* an escalation-risk score in [0, 1] with a short explanation,
* a human-review flag, and
* a sentiment trend derived from prior customer turns when enough
  history exists (``"unknown"`` otherwise).

Public interface::

    from backend.agents.intent_sentiment_agent import analyze_message

    result = analyze_message("My payment failed twice, please help.")

The class :class:`IntentSentimentAgent` also exposes ``run(session,
message) -> AgentResult``, the standard orchestrator entry point used by
``backend.orchestrator.run_workflow``.

METHOD NOTE (important): classification is **rule-based** — transparent
keyword lexicons, weighted evidence scoring, and hand-tuned thresholds
defined in :mod:`backend.agents.intent_sentiment_config`.  It is NOT a
trained machine-learning model, and its confidence values are heuristic
evidence shares, NOT calibrated probabilities.  See
``docs/intent_sentiment_agent.md`` for limitations.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Final, Literal

from pydantic import ConfigDict, Field, ValidationError

from backend.agents.intent_sentiment_config import (
    DEFAULT_FALLBACK_INTENT,
    DEFAULT_INTENT_KEYWORDS,
    DEFAULT_SCORING_CONFIG,
    EMOTION_INDICATORS,
    ESCALATION_TRIGGERS,
    FALLBACK_GENERAL_CUES,
    GENERAL_INQUIRY_INTENT,
    INTENSIFIER_MULTIPLIER,
    INTENSIFIER_WINDOW_TOKENS,
    INTENSIFIERS,
    NEGATION_WINDOW_TOKENS,
    NEGATION_WORDS,
    NEGATIVE_TERMS,
    POSITIVE_TERMS,
    REPEAT_MARKERS,
    REPEAT_REGEXES,
    ScoringConfig,
    compile_lexicon,
    compile_term,
)
from backend.core.data_models import AgentResult
from backend.orchestrator.agent_contracts import AgentError, CustomerMessage, SentimentResult
from backend.orchestrator.knowledge_schemas import ConversationHistoryItem

logger = logging.getLogger(__name__)

AGENT_TYPE: Final[str] = "intent-sentiment-analysis-agent"

EmotionLabel = Literal[
    "frustration",
    "anger",
    "confusion",
    "disappointment",
    "satisfaction",
    "urgency",
    "neutral",
]

SentimentTrend = Literal["improving", "stable", "worsening", "unknown"]

_SAFE_ID_PATTERN = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------


class IntentSentimentResult(SentimentResult):
    """Structured output of the Intent and Sentiment Analysis Agent.

    Extends the shared Milestone 2 :class:`SentimentResult` contract
    (``backend.orchestrator.agent_contracts``) with the coaching fields
    this agent is responsible for, so any caller that accepts a
    ``SentimentResult`` also accepts this model.
    """

    model_config = ConfigDict(extra="forbid")

    emotion: list[EmotionLabel] = Field(
        min_length=1,
        description="Detected emotion indicators; a message may show several.",
    )
    frustration_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Heuristic frustration estimate in [0, 1].",
    )
    escalation_risk_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Heuristic escalation-risk estimate in [0, 1].",
    )
    requires_human_review: bool = Field(
        description="True when escalation risk reaches the review threshold.",
    )
    explanation: str = Field(
        min_length=1,
        max_length=500,
        description="Short, content-safe explanation of the risk assessment.",
    )
    sentiment_trend: SentimentTrend = Field(
        default="unknown",
        description=(
            "Direction of sentiment across prior customer turns, or "
            "'unknown' when history is insufficient."
        ),
    )

    def to_agent_result(self, session_id: str | None = None) -> AgentResult:
        """Convert to the shared ``AgentResult`` dataclass for the orchestrator."""
        return AgentResult(
            session_id=_sanitize_session_id(session_id),
            agent_type=AGENT_TYPE,
            result=self.model_dump(mode="json"),
        )


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------


def _clamp01(value: float) -> float:
    """Clamp a score into [0, 1]."""
    return max(0.0, min(1.0, value))


def _saturation(evidence: float, half_life: float) -> float:
    """Diminishing-returns curve mapping evidence to [0, 1).

    ``half_life`` is the evidence value that scores 0.5.
    """
    if evidence <= 0:
        return 0.0
    return evidence / (evidence + half_life)


def _evidence_confidence(support: float, opposing: float, prior: float) -> float:
    """Heuristic confidence from supporting vs. opposing keyword evidence.

    ``support / (support + prior)`` rewards absolute evidence volume and
    ``support / (support + opposing)`` rewards dominance over the
    runner-up.  The product is bounded to [0, 1] but is an evidence
    share, not a calibrated probability.
    """
    if support <= 0:
        return 0.0
    strength = support / (support + prior)
    dominance = support / (support + max(opposing, 0.0))
    return round(_clamp01(strength * dominance), 4)


def _overlaps(span: tuple[int, int], consumed: list[tuple[int, int]]) -> bool:
    """True when ``span`` intersects any already-consumed span."""
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in consumed)


def _tokens_before(text: str, position: int, count: int) -> list[str]:
    """Return the last ``count`` word tokens occurring before ``position``."""
    tokens = _TOKEN_PATTERN.findall(text[:position].lower())
    return tokens[-count:] if count > 0 else []


def _sanitize_session_id(value: Any) -> str:
    """Return a session id that satisfies the shared ``AgentResult`` rules."""
    sid = str(value).strip() if value is not None else ""
    if not _SAFE_ID_PATTERN.fullmatch(sid):
        return "sess-default"
    return sid


def _safe_validation_summary(exc: ValidationError) -> list[dict[str, str]]:
    """Extract field/reason pairs without echoing raw customer input."""
    issues: list[dict[str, str]] = []
    for error in exc.errors()[:5]:
        issues.append(
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "reason": str(error.get("msg", "")),
            }
        )
    return issues


def _has_fallback_general_cue(text_lower: str) -> bool:
    """True when a message without intent keywords still looks like a question/greeting."""
    if "?" in text_lower:
        return True
    for cue in FALLBACK_GENERAL_CUES:
        if cue.isalpha() and re.search(rf"\b{re.escape(cue)}\b", text_lower):
            return True
    return False


def _normalize_history(conversation_history: Any) -> list[ConversationHistoryItem]:
    """Coerce mixed history inputs into validated ``ConversationHistoryItem``s.

    Accepts ``None``, a single mapping/dataclass, or a sequence of
    mappings (``content``/``text`` + ``speaker``/``role``),
    ``ConversationHistoryItem`` objects, or ``ConversationMessage``
    dataclasses.  Malformed entries are skipped so optional context can
    never break the analysis.
    """
    if conversation_history is None:
        return []

    if isinstance(conversation_history, (str, bytes)):
        raise TypeError(
            "conversation_history must be a sequence of messages, not a string."
        )

    if isinstance(conversation_history, (list, tuple)):
        raw_items: list[Any] = list(conversation_history)
    elif isinstance(conversation_history, ConversationHistoryItem) or isinstance(
        conversation_history, dict
    ) or hasattr(conversation_history, "to_dict"):
        raw_items = [conversation_history]
    else:
        raise TypeError(
            "conversation_history must be a sequence of messages; got "
            f"{type(conversation_history).__name__}."
        )

    normalized: list[ConversationHistoryItem] = []
    for raw in raw_items:
        if isinstance(raw, ConversationHistoryItem):
            normalized.append(raw)
            continue
        if hasattr(raw, "to_dict"):
            raw = raw.to_dict()
        if not isinstance(raw, dict):
            continue

        content = raw.get("content")
        if content is None:
            content = raw.get("text")
        speaker = raw.get("speaker") or raw.get("role") or "customer"
        turn = raw.get("turn_number")
        if turn is None:
            turn = raw.get("turn")
        if isinstance(turn, bool) or not isinstance(turn, int) or turn < 1:
            turn = None

        if not isinstance(content, str) or not content.strip():
            continue

        try:
            normalized.append(
                ConversationHistoryItem(
                    speaker=speaker, content=content, turn_number=turn
                )
            )
        except ValidationError:
            # Unknown speaker label: skip rather than fail the analysis.
            continue
    return normalized


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class IntentSentimentAgent:
    """Rule-based Intent and Sentiment Analysis Agent.

    Parameters
    ----------
    intent_keywords:
        Optional replacement mapping of ``label -> keywords``.  Labels
        become the configurable intent set; declaration order breaks
        keyword-score ties.  Defaults to
        :data:`DEFAULT_INTENT_KEYWORDS`.
    config:
        Optional :class:`ScoringConfig` overriding weights/thresholds.

    The instance is stateless after construction, so ``analyze`` is
    deterministic and safe to call concurrently.
    """

    AGENT_TYPE: Final[str] = AGENT_TYPE

    def __init__(
        self,
        intent_keywords: dict[str, tuple[str, ...]] | None = None,
        config: ScoringConfig | None = None,
    ) -> None:
        self.config: Final[ScoringConfig] = config or DEFAULT_SCORING_CONFIG

        if intent_keywords is None:
            keywords = dict(DEFAULT_INTENT_KEYWORDS)
        else:
            keywords = dict(intent_keywords)
        if not keywords:
            raise ValueError("intent_keywords must define at least one intent label.")
        for label, terms in keywords.items():
            if not isinstance(label, str) or not label.strip():
                raise ValueError("Every intent label must be a non-empty string.")
            if not isinstance(terms, (list, tuple)) or not terms:
                raise ValueError(
                    f"Intent label {label!r} must map to a non-empty sequence of keywords."
                )
            for term in terms:
                if not isinstance(term, str) or not term.strip():
                    raise ValueError(
                        f"Intent label {label!r} contains an empty keyword entry."
                    )
        self._intent_labels: Final[tuple[str, ...]] = tuple(keywords)
        # label -> (phrase pairs, word pairs) with declaration order preserved.
        self._intent_index: Final[dict[str, tuple[list, list]]] = {
            label: self._split_phrases({t: 1.0 for t in terms})
            for label, terms in keywords.items()
        }

        # Sentiment lexicons, split so phrases suppress overlapping words.
        self._phrase_index: Final[list[tuple[re.Pattern[str], float, int]]] = [
            *[(p, w, +1) for p, w in self._split_phrases(POSITIVE_TERMS)[0]],
            *[(p, w, -1) for p, w in self._split_phrases(NEGATIVE_TERMS)[0]],
        ]
        self._word_index: Final[list[tuple[re.Pattern[str], float, int]]] = [
            *[(p, w, +1) for p, w in self._split_phrases(POSITIVE_TERMS)[1]],
            *[(p, w, -1) for p, w in self._split_phrases(NEGATIVE_TERMS)[1]],
        ]

        # Emotion indicator patterns per emotion label.
        self._emotion_index: Final[dict[str, list[re.Pattern[str]]]] = {
            name: [pattern for pattern, _ in compile_lexicon(terms)]
            for name, terms in EMOTION_INDICATORS.items()
        }

        # Escalation trigger patterns with severities (longest first).
        self._trigger_index: Final[list[tuple[re.Pattern[str], float]]] = [
            (pattern, severity)
            for pattern, severity in sorted(
                (
                    (compile_term(term), severity)
                    for term, severity in ESCALATION_TRIGGERS.items()
                ),
                key=lambda pair: len(pair[0].pattern),
                reverse=True,
            )
        ]

        # Frustration cue patterns (deduplicated union of cue lexicons).
        cue_terms = dict.fromkeys(
            [*EMOTION_INDICATORS["frustration"], *REPEAT_MARKERS]
        )
        self._cue_patterns: Final[list[re.Pattern[str]]] = [
            pattern for pattern, _ in compile_lexicon(tuple(cue_terms))
        ]

        # Repeat markers: plain terms plus supplementary regexes.
        repeat_patterns = [pattern for pattern, _ in compile_lexicon(REPEAT_MARKERS)]
        repeat_patterns.extend(re.compile(rx, re.IGNORECASE) for rx in REPEAT_REGEXES)
        self._repeat_patterns: Final[list[re.Pattern[str]]] = repeat_patterns

        self._urgency_patterns: Final[list[re.Pattern[str]]] = list(
            self._emotion_index.get("urgency", [])
        )

    # -- lexicon helpers ---------------------------------------------------

    @staticmethod
    def _split_phrases(
        lexicon: dict[str, float],
    ) -> tuple[list[tuple[re.Pattern[str], float]], list[tuple[re.Pattern[str], float]]]:
        """Split a lexicon into (phrases, words), each longest-first."""
        phrases = {term: w for term, w in lexicon.items() if " " in term}
        words = {term: w for term, w in lexicon.items() if " " not in term}
        return compile_lexicon(phrases), compile_lexicon(words)

    # -- sentiment ---------------------------------------------------------

    def _polarity_evidence(self, text: str) -> tuple[float, float]:
        """Return (positive, negative) evidence weights for ``text``.

        Multi-word phrases are matched first and consume their span so a
        phrase like "not working" is not double-counted against the word
        "working".  Single-word hits are flipped by a preceding negation
        and amplified by a preceding intensifier.
        """
        positive = 0.0
        negative = 0.0
        consumed: list[tuple[int, int]] = []

        for pattern, weight, sign in self._phrase_index:
            for match in pattern.finditer(text):
                span = match.span()
                if _overlaps(span, consumed):
                    continue
                consumed.append(span)
                if sign > 0:
                    positive += weight
                else:
                    negative += weight

        for pattern, weight, sign in self._word_index:
            for match in pattern.finditer(text):
                span = match.span()
                if _overlaps(span, consumed):
                    continue
                consumed.append(span)

                window = _tokens_before(text, match.start(), NEGATION_WINDOW_TOKENS)
                polarity = sign
                if any(token in NEGATION_WORDS for token in window):
                    polarity = -polarity

                adjusted = weight
                intensifier_window = _tokens_before(
                    text, match.start(), INTENSIFIER_WINDOW_TOKENS
                )
                if any(token in INTENSIFIERS for token in intensifier_window):
                    adjusted *= INTENSIFIER_MULTIPLIER

                if polarity > 0:
                    positive += adjusted
                else:
                    negative += adjusted

        return positive, negative

    def _classify_sentiment(
        self, positive: float, negative: float
    ) -> tuple[str, float, float]:
        """Return (label, confidence, polarity) from evidence weights."""
        total = positive + negative
        if total <= 0:
            return (
                "neutral",
                round(self.config.neutral_fallback_confidence, 4),
                0.0,
            )

        polarity = (positive - negative) / total
        opposing = 0.0
        if positive > 0 and negative > 0:
            ratio = min(positive, negative) / max(positive, negative)
            if ratio >= self.config.mixed_sentiment_ratio:
                label = "mixed"
                support = min(positive, negative)
                opposing = abs(positive - negative)
            elif positive > negative:
                label = "positive"
                support = positive
                opposing = negative
            else:
                label = "negative"
                support = negative
                opposing = positive
        elif positive > 0:
            label = "positive"
            support = positive
        else:
            label = "negative"
            support = negative

        confidence = _evidence_confidence(
            support, opposing, self.config.confidence_prior
        )
        return label, confidence, polarity

    # -- intent ------------------------------------------------------------

    def _classify_intent(self, text: str) -> tuple[str, float]:
        """Return (intent label, heuristic confidence) for ``text``."""
        scores: dict[str, float] = {}
        for label, (phrases, words) in self._intent_index.items():
            score = 0.0
            consumed: list[tuple[int, int]] = []
            for pattern, weight in phrases:
                for match in pattern.finditer(text):
                    span = match.span()
                    if _overlaps(span, consumed):
                        continue
                    consumed.append(span)
                    score += weight
            for pattern, weight in words:
                for match in pattern.finditer(text):
                    span = match.span()
                    if _overlaps(span, consumed):
                        continue
                    consumed.append(span)
                    score += weight
            scores[label] = score

        best_label: str | None = None
        best_score = 0.0
        for label in self._intent_labels:  # declaration order breaks ties
            if scores[label] > best_score:
                best_score = scores[label]
                best_label = label

        if best_label is None:
            text_lower = text.lower()
            if _has_fallback_general_cue(text_lower):
                return (
                    GENERAL_INQUIRY_INTENT,
                    round(self.config.general_inquiry_fallback_confidence, 4),
                )
            return (
                DEFAULT_FALLBACK_INTENT,
                round(self.config.other_fallback_confidence, 4),
            )

        opposing = max(
            (score for label, score in scores.items() if label != best_label),
            default=0.0,
        )
        confidence = _evidence_confidence(
            best_score, opposing, self.config.confidence_prior
        )
        return best_label, confidence

    # -- emotions ----------------------------------------------------------

    def _detect_emotions(self, text: str) -> list[str]:
        """Return every emotion indicator present in ``text`` (config order)."""
        detected = [
            label
            for label, patterns in self._emotion_index.items()
            if any(pattern.search(text) for pattern in patterns)
        ]
        return detected or ["neutral"]

    # -- frustration, repeat, escalation -----------------------------------

    def _repeat_signal(self, text: str, prior_intents: list[str], current_intent: str) -> float:
        """Evidence that the same issue keeps coming back, in [0, 1].

        Combines in-message markers ("third time", "4 times contacted")
        with the number of prior customer turns classified into the same
        intent as the current message.  Heuristic: a customer repeating a
        request is treated as an unresolved issue.
        """
        marker_count = sum(
            1 for pattern in self._repeat_patterns if pattern.search(text)
        )
        message_signal = _clamp01(
            marker_count / self.config.repeat_evidence_for_full_signal
        )
        same_intent = sum(1 for label in prior_intents if label == current_intent)
        history_signal = _clamp01(
            same_intent / self.config.repeat_evidence_for_full_signal
        )
        return max(message_signal, history_signal)

    def _frustration_score(
        self,
        text: str,
        positive: float,
        negative: float,
        repeat_signal: float,
    ) -> float:
        """Heuristic frustration score in [0, 1]."""
        cfg = self.config
        negative_sat = _saturation(negative, cfg.negative_saturation_half)
        cue_count = sum(1 for pattern in self._cue_patterns if pattern.search(text))
        cue_sat = _saturation(cue_count, cfg.cue_saturation_half)

        bangs = text.count("!")
        shouty_words = len(re.findall(r"\b[A-Z]{4,}\b", text))
        format_signal = (0.5 if bangs >= 2 else 0.0) + (
            0.5 if shouty_words >= 2 else 0.0
        )

        positive_sat = _saturation(positive, cfg.negative_saturation_half)

        value = (
            cfg.frustration_weight_negative * negative_sat
            + cfg.frustration_weight_cues * cue_sat
            + cfg.frustration_weight_format * format_signal
            + cfg.frustration_weight_repeat * repeat_signal
            - cfg.frustration_positive_relief * positive_sat
        )
        return round(_clamp01(value), 4)

    def _trigger_score(self, text: str) -> float:
        """Highest severity among matched escalation triggers, in [0, 1]."""
        best = 0.0
        for pattern, severity in self._trigger_index:
            if severity > best and pattern.search(text):
                best = severity
        return best

    def _escalation_risk(
        self,
        frustration: float,
        trigger_score: float,
        repeat_signal: float,
        urgency_evidence: int,
    ) -> float:
        """Heuristic escalation-risk score in [0, 1].

        Negative sentiment alone caps at ``risk_weight_frustration`` +
        ``risk_weight_urgency`` (0.45 by default), which is below the
        review threshold, so human review always requires explicit
        escalation language or repeat-contact evidence.
        """
        cfg = self.config
        urgency_sat = _saturation(urgency_evidence, cfg.urgency_saturation_half)
        value = (
            cfg.risk_weight_frustration * frustration
            + cfg.risk_weight_trigger * trigger_score
            + cfg.risk_weight_repeat * repeat_signal
            + cfg.risk_weight_urgency * urgency_sat
        )
        return round(_clamp01(value), 4)

    # -- trend -------------------------------------------------------------

    def _sentiment_trend(
        self, prior_polarities: list[float], current_polarity: float
    ) -> str:
        """Direction of sentiment across the conversation.

        Requires at least ``min_history_for_trend`` prior customer
        messages; otherwise returns ``"unknown"`` (no trend is claimed
        without sufficient history).
        """
        if len(prior_polarities) < self.config.min_history_for_trend:
            return "unknown"

        points = [*prior_polarities, current_polarity]
        split = len(points) // 2
        earlier = sum(points[:split]) / split
        later = sum(points[split:]) / (len(points) - split)
        delta = later - earlier
        if delta >= self.config.trend_epsilon:
            return "improving"
        if delta <= -self.config.trend_epsilon:
            return "worsening"
        return "stable"

    # -- explanation -------------------------------------------------------

    def _build_explanation(
        self,
        sentiment: str,
        frustration: float,
        trigger_score: float,
        repeat_signal: float,
        urgency_evidence: int,
        trend: str,
        requires_review: bool,
    ) -> str:
        """Compose a short explanation from scoring signals only.

        Never echoes customer message content, so it is safe to log.
        """
        reasons: list[str] = []
        if trigger_score >= 1.0:
            reasons.append("explicit legal, regulatory or financial threats")
        elif trigger_score >= 0.9:
            reasons.append("a threat to escalate publicly")
        elif trigger_score > 0.0:
            reasons.append("an explicit request for escalation")
        if repeat_signal >= 1.0:
            reasons.append("the customer has raised this issue repeatedly")
        elif repeat_signal > 0.0:
            reasons.append("the message suggests a recurring issue")
        if frustration >= 0.6:
            reasons.append("strong frustrated language")
        if sentiment == "negative":
            reasons.append("a negative tone")
        if trend == "worsening":
            reasons.append("a worsening sentiment trend")
        if urgency_evidence > 0:
            reasons.append("time pressure")

        if not reasons:
            return "No strong escalation signals were detected."

        explanation = "Escalation risk factors: " + ", ".join(reasons) + "."
        if requires_review:
            explanation += " Human review recommended."
        return explanation

    # -- public API --------------------------------------------------------

    def analyze(
        self,
        message: str | CustomerMessage,
        conversation_history: Any = None,
    ) -> IntentSentimentResult:
        """Analyse one customer message.

        Parameters
        ----------
        message:
            The customer message as a string, or a pre-validated
            :class:`CustomerMessage`.
        conversation_history:
            Optional prior turns (mappings, ``ConversationHistoryItem``
            objects, or ``ConversationMessage`` dataclasses).  Used for
            the sentiment trend and recurring-issue detection.

        Returns
        -------
        IntentSentimentResult
            Validated, JSON-serialisable analysis.

        Raises
        ------
        pydantic.ValidationError
            If the message is missing, empty, whitespace-only, or not a
            string.
        TypeError
            If ``conversation_history`` is not a supported container.
        """
        history = _normalize_history(conversation_history)

        if isinstance(message, CustomerMessage):
            customer = message
        else:
            prior_turns = [item.turn_number for item in history if item.turn_number]
            next_turn = (max(prior_turns) + 1) if prior_turns else 1
            customer = CustomerMessage(content=message, turn_number=next_turn)

        cfg = self.config
        text = customer.content[: cfg.max_analysis_chars]

        positive, negative = self._polarity_evidence(text)
        sentiment, sentiment_confidence, polarity = self._classify_sentiment(
            positive, negative
        )
        intent, intent_confidence = self._classify_intent(text)
        emotions = self._detect_emotions(text)

        customer_priors = [
            item.content for item in history if item.speaker == "customer"
        ][-cfg.history_window :]
        prior_texts = [content[: cfg.max_analysis_chars] for content in customer_priors]
        prior_intents = [self._classify_intent(text)[0] for text in prior_texts]

        repeat_signal = self._repeat_signal(text, prior_intents, intent)
        frustration = self._frustration_score(text, positive, negative, repeat_signal)
        trigger_score = self._trigger_score(text)
        urgency_evidence = sum(
            1 for pattern in self._urgency_patterns if pattern.search(text)
        )
        risk = self._escalation_risk(
            frustration, trigger_score, repeat_signal, urgency_evidence
        )
        requires_review = risk >= cfg.human_review_risk_threshold

        prior_polarities = []
        for prior_text in prior_texts:
            pos, neg = self._polarity_evidence(prior_text)
            prior_polarities.append(
                (pos - neg) / (pos + neg) if (pos + neg) > 0 else 0.0
            )
        trend = self._sentiment_trend(prior_polarities, polarity)

        explanation = self._build_explanation(
            sentiment=sentiment,
            frustration=frustration,
            trigger_score=trigger_score,
            repeat_signal=repeat_signal,
            urgency_evidence=urgency_evidence,
            trend=trend,
            requires_review=requires_review,
        )

        logger.debug(
            "Analysis complete | intent=%s | sentiment=%s | review=%s | message_length=%d",
            intent,
            sentiment,
            requires_review,
            len(customer.content),
        )

        return IntentSentimentResult(
            sentiment=sentiment,
            confidence=sentiment_confidence,
            intent=intent,
            intent_confidence=intent_confidence,
            emotion=emotions,
            frustration_score=frustration,
            escalation_risk_score=risk,
            requires_human_review=requires_review,
            explanation=explanation,
            sentiment_trend=trend,
        )

    # -- orchestrator entry point -----------------------------------------

    @staticmethod
    def _history_from_session(session: Any) -> list:
        """Best-effort extraction of prior turns from a Session object.

        Looks at ``session.metadata['conversation_history']`` (or
        ``'history'``) and falls back to ``session.replay_transcript``.
        Returns ``[]`` when the session carries no history.
        """
        if session is None:
            return []
        metadata = getattr(session, "metadata", None)
        history = None
        if isinstance(metadata, dict):
            history = metadata.get("conversation_history") or metadata.get("history")
        if not history:
            transcript = getattr(session, "replay_transcript", None)
            if isinstance(transcript, (list, tuple)) and transcript:
                history = transcript
        if isinstance(history, (list, tuple)):
            return list(history)
        return []

    def run(self, session: Any, message: str) -> AgentResult:
        """Standard orchestrator entry point: ``run(session, message)``.

        Never raises.  Input-validation failures and unexpected errors
        are converted into an ``AgentError`` inside a non-empty
        ``AgentResult.result`` (``{"status": "failed", "errors": [...]}``),
        matching the Milestone 2 error contract while keeping the
        orchestrator's "non-empty result" requirement satisfied.
        """
        session_id = _sanitize_session_id(getattr(session, "session_id", None))
        try:
            history = self._history_from_session(session)
            result = self.analyze(message, conversation_history=history)
            return result.to_agent_result(session_id=session_id)
        except ValidationError as exc:
            issues = _safe_validation_summary(exc)
            logger.warning(
                "Input rejected | session_id=%s | fields=%s",
                session_id,
                [issue["field"] for issue in issues],
            )
            error = AgentError(
                agent_name=AGENT_TYPE,
                code="INVALID_INPUT",
                message="Customer message failed validation.",
                retryable=False,
                details={"issues": issues},
            )
            return self._failed_result(session_id, error)
        except Exception:
            # Do not log message content; tracebacks reference code, not data.
            logger.exception("Analysis failed | session_id=%s", session_id)
            error = AgentError(
                agent_name=AGENT_TYPE,
                code="ANALYSIS_FAILED",
                message="Intent and sentiment analysis failed unexpectedly.",
                retryable=True,
            )
            return self._failed_result(session_id, error)

    @staticmethod
    def _failed_result(session_id: str, error: AgentError) -> AgentResult:
        """Build a non-empty AgentResult carrying an AgentError payload."""
        return AgentResult(
            session_id=session_id,
            agent_type=AGENT_TYPE,
            result={"status": "failed", "errors": [error.model_dump(mode="json")]},
        )


_DEFAULT_AGENT = IntentSentimentAgent()


def analyze_message(
    message: str | CustomerMessage,
    conversation_history: Any = None,
) -> IntentSentimentResult:
    """Analyse one customer message with the default configuration.

    Parameters
    ----------
    message:
        Customer message text (or a pre-built ``CustomerMessage``).
        Empty or whitespace-only messages raise
        ``pydantic.ValidationError``.
    conversation_history:
        Optional prior turns used for the sentiment trend and
        recurring-issue detection.  ``None`` means "no history"; the
        trend is then reported as ``"unknown"``.

    Returns
    -------
    IntentSentimentResult

    Examples
    --------
    >>> result = analyze_message("Where is my order? It has not arrived.")
    >>> result.intent in {"order_or_service_status", "other"}
    True
    >>> 0.0 <= result.frustration_score <= 1.0
    True
    """
    return _DEFAULT_AGENT.analyze(message, conversation_history)


__all__ = [
    "AGENT_TYPE",
    "EmotionLabel",
    "IntentSentimentAgent",
    "IntentSentimentResult",
    "SentimentTrend",
    "analyze_message",
]
