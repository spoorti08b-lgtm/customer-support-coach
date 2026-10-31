"""Configuration for the Intent and Sentiment Analysis Agent.

Every lexicon, scoring weight, and threshold used by the rule-based
analysis lives in this module so that classification logic in
``intent_sentiment_agent.py`` stays free of hard-coded magic numbers and
the team can tune behaviour without touching business logic.

IMPORTANT: everything below is a hand-authored heuristic aid.  These are
NOT parameters of a trained machine-learning model and the confidences
derived from them are NOT calibrated probabilities.  See
``docs/intent_sentiment_agent.md`` for the documented limitations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Intent labels and keyword evidence
# ---------------------------------------------------------------------------

# Declaration order matters: keyword ties are resolved in favour of the
# label declared first, so specific intents are listed before the
# generic "general_inquiry" catch-all.
DEFAULT_INTENT_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "billing_or_payment": (
        "billing", "invoice", "payment", "payments", "pay", "charged",
        "charge", "overcharged", "double charged", "extra charge",
        "credit card", "debit card", "card declined", "declined",
        "transaction", "receipt", "autopay", "auto pay", "direct debit",
        "fee", "fees", "bank",
    ),
    "technical_issue": (
        "error", "errors", "bug", "crash", "crashes", "crashing",
        "not working", "doesn't work", "does not work", "won't load",
        "will not load", "loading", "stuck", "frozen", "freeze",
        "glitch", "outage", "server down", "site down", "app down",
        "slow", "lag", "lagging", "fails", "failed", "failure",
        "broken", "uninstall", "reinstall", "sync", "install",
        "installation", "timeout", "update", "upgrade",
    ),
    "account_access": (
        "login", "log in", "signin", "sign in", "sign-in", "password",
        "locked out", "account locked", "locked", "can't log",
        "cannot log", "2fa", "two-factor", "verification code",
        "username", "authentication", "otp", "access my account",
        "can't access", "cannot access", "blocked", "reset my",
    ),
    "refund_or_cancellation": (
        "refund", "refunds", "cancel", "cancellation", "cancelling",
        "unsubscribe", "close my account", "terminate my",
        "money back", "chargeback", "return", "returns", "returned",
        "exchange", "stop my subscription", "reverse the charge",
    ),
    "order_or_service_status": (
        "order", "orders", "delivery", "delivered", "shipping",
        "tracking", "track", "package", "parcel", "shipment",
        "arrive", "arrived", "dispatched", "courier", "where is",
        "when will", "eta", "status of", "on the way",
        "estimated delivery", "waiting for my",
    ),
    "product_information": (
        "does it", "specification", "specifications", "specs",
        "feature", "features", "compatible", "compatibility",
        "warranty", "dimensions", "availability", "in stock",
        "compare", "comparison", "difference between", "manual",
        "instructions", "how long does", "what is the", "how many",
        "size",
    ),
    "complaint": (
        "complaint", "complain", "complaining", "unacceptable",
        "poor service", "bad service", "terrible service",
        "worst service", "dissatisfied", "formal complaint",
        "file a complaint", "raise a complaint", "waste of time",
    ),
    "general_inquiry": (
        "how do i", "how can i", "could you", "would you", "may i",
        "question", "questions", "enquiry", "inquiry", "wondering",
        "information about", "tell me", "hello", "hi", "hey",
        "good morning", "good afternoon", "good evening",
        "thank you", "thanks",
    ),
}

DEFAULT_FALLBACK_INTENT: Final[str] = "other"
GENERAL_INQUIRY_INTENT: Final[str] = "general_inquiry"

# Question / greeting cues used only when NO intent keyword matched, to
# choose between the two low-confidence fallback labels.
FALLBACK_GENERAL_CUES: Final[tuple[str, ...]] = (
    "?", "how", "what", "when", "where", "why", "who", "which",
    "is", "are", "can", "could", "would", "do", "does", "did",
    "hello", "hi", "hey", "please",
)

# ---------------------------------------------------------------------------
# Sentiment lexicon
# ---------------------------------------------------------------------------

# term -> evidence weight.  Multi-word phrases are allowed; whitespace in
# the message is matched flexibly.  Weights > 1.0 mark strong polarity.
POSITIVE_TERMS: Final[dict[str, float]] = {
    "thank you": 1.0,
    "thanks": 1.0,
    "much appreciated": 1.5,
    "appreciate": 1.0,
    "appreciated": 1.0,
    "grateful": 1.0,
    "great": 1.0,
    "good": 1.0,
    "excellent": 1.5,
    "wonderful": 1.5,
    "fantastic": 1.5,
    "awesome": 1.5,
    "amazing": 1.5,
    "perfect": 1.5,
    "love": 1.5,
    "happy": 1.5,
    "pleased": 1.0,
    "glad": 1.0,
    "delighted": 1.5,
    "helpful": 1.0,
    "helped": 1.0,
    "resolved": 1.5,
    "fixed": 1.0,
    "works": 1.0,
    "working": 1.0,
    "works now": 1.5,
    "all good": 1.5,
    "nice": 1.0,
    "easy": 1.0,
    "fast": 1.0,
    "quick": 1.0,
    "smooth": 1.0,
    "reliable": 1.0,
    "satisfied": 1.5,
    "impressed": 1.0,
    "brilliant": 1.5,
    "friendly": 1.0,
    "professional": 1.0,
}

NEGATIVE_TERMS: Final[dict[str, float]] = {
    # multi-word phrases first at compile time (longest match wins)
    "not working": 1.5,
    "doesn't work": 1.5,
    "did not work": 1.5,
    "didn't work": 1.5,
    "won't work": 1.5,
    "not fixed": 1.5,
    "still broken": 1.5,
    "no response": 1.5,
    "no reply": 1.5,
    "never again": 1.5,
    "still waiting": 1.5,
    "waste of time": 1.5,
    "taking forever": 1.5,
    "keep getting": 1.5,
    "keeps crashing": 1.5,
    "can't log in": 1.5,
    "cannot log in": 1.5,
    "can't access": 1.5,
    "cannot access": 1.5,
    "nothing works": 1.5,
    "same issue": 1.5,
    "same problem": 1.5,
    "not received": 1.5,
    "hasn't arrived": 1.5,
    "has not arrived": 1.5,
    "never arrived": 1.5,
    "charged twice": 1.5,
    "double charged": 1.5,
    "overcharged": 1.5,
    "not helpful": 1.5,
    "no help": 1.5,
    "no one": 1.0,
    # single words
    "bad": 1.0,
    "poor": 1.0,
    "slow": 1.0,
    "late": 1.0,
    "delayed": 1.0,
    "stuck": 1.0,
    "broken": 1.0,
    "rude": 1.0,
    "unhelpful": 1.0,
    "annoyed": 1.0,
    "annoying": 1.0,
    "frustrated": 1.0,
    "frustrating": 1.0,
    "confused": 1.0,
    "confusing": 1.0,
    "disappointed": 1.0,
    "disappointing": 1.0,
    "unacceptable": 1.5,
    "ridiculous": 1.5,
    "terrible": 1.5,
    "awful": 1.5,
    "horrible": 1.5,
    "worst": 1.5,
    "hate": 1.5,
    "angry": 1.5,
    "furious": 1.5,
    "useless": 1.5,
    "pathetic": 1.5,
    "garbage": 1.5,
    "scam": 1.5,
    "fraud": 1.5,
    "nightmare": 1.5,
    "dissatisfied": 1.0,
}

# Words that flip the polarity of a sentiment term within the window.
# Only pre-adjective negators belong here.  Indeterminate pronouns such as
# "nothing"/"nobody"/"nowhere" are excluded: "nothing works" is handled
# as a phrase, while "nothing ... awful" must NOT be read as praise.
NEGATION_WORDS: Final[frozenset[str]] = frozenset({
    "not", "no", "never", "neither", "nor",
    "cannot", "can't", "won't", "doesn't", "didn't", "isn't",
    "aren't", "wasn't", "weren't", "don't", "hasn't", "haven't",
    "hadn't", "without",
})

# Words that amplify a sentiment term inside the window.
INTENSIFIERS: Final[frozenset[str]] = frozenset({
    "very", "extremely", "really", "so", "totally", "absolutely",
    "incredibly", "utterly", "highly", "deeply", "strongly",
})

NEGATION_WINDOW_TOKENS: Final[int] = 3
INTENSIFIER_WINDOW_TOKENS: Final[int] = 2
INTENSIFIER_MULTIPLIER: Final[float] = 1.5

# ---------------------------------------------------------------------------
# Emotion indicators (a message may match several)
# ---------------------------------------------------------------------------

EMOTION_INDICATORS: Final[dict[str, tuple[str, ...]]] = {
    "frustration": (
        "frustrated", "frustration", "frustrating", "fed up",
        "sick of", "tired of", "keep getting", "keeps happening",
        "again and again", "still waiting", "no progress",
        "nothing works", "same issue", "same problem", "third time",
        "fourth time", "fifth time", "every time", "not resolved",
        "still not", "can't get", "cannot get",        "no one has", "unacceptable", "ridiculous", "pointless",
        "worst", "useless", "pathetic", "waste of time",
        "fed-up", "annoying",
    ),
    "anger": (
        "angry", "furious", "infuriating", "infuriated", "outraged",
        "livid", "seething", "mad", "rage", "fume", "hate",
    ),
    "confusion": (
        "confused", "confusing", "don't understand", "do not understand",
        "not sure what", "unclear", "what does", "how do i", "why is",
        "explain", "baffled", "perplexed", "lost", "no idea",
    ),
    "disappointment": (
        "disappointed", "disappointing", "let down", "expected better",
        "not what i expected", "regret", "unfortunately", "sadly",
    ),
    "satisfaction": (
        "thank", "thanks", "appreciate", "great", "perfect",
        "resolved", "fixed", "happy", "glad", "pleased", "works now",
        "all good", "much appreciated", "grateful", "satisfied",
    ),
    "urgency": (
        "urgent", "urgently", "immediately", "asap", "right away",
        "today", "deadline", "emergency", "quickly", "hurry",
        "time-sensitive", "by tomorrow", "end of the day",
    ),
}

# ---------------------------------------------------------------------------
# Escalation triggers (term -> severity in [0, 1])
# ---------------------------------------------------------------------------

ESCALATION_TRIGGERS: Final[dict[str, float]] = {
    # Explicit requests for escalation (severity 0.8)
    "manager": 0.8,
    "supervisor": 0.8,
    "escalate": 0.8,
    "escalation": 0.8,
    "head office": 0.8,
    "corporate office": 0.8,
    "higher up": 0.8,
    "file a complaint": 0.8,
    "formal complaint": 0.8,
    "raise a complaint": 0.8,
    "cancel my account": 0.8,
    "close my account": 0.8,
    "delete my account": 0.8,
    "never using again": 0.8,
    "never buying again": 0.8,
    # Public exposure threats (severity 0.9)
    "social media": 0.9,
    "twitter": 0.9,
    "facebook": 0.9,
    "instagram": 0.9,
    "publicly": 0.9,
    "post this online": 0.9,
    # Legal / regulatory / financial threats (severity 1.0)
    "lawyer": 1.0,
    "attorney": 1.0,
    "lawsuit": 1.0,
    "sue": 1.0,
    "suing": 1.0,
    "legal action": 1.0,
    "court": 1.0,
    "police": 1.0,
    "regulatory": 1.0,
    "ombudsman": 1.0,
    "consumer affairs": 1.0,
    "chargeback": 1.0,
    "dispute the charge": 1.0,
    "report you": 1.0,
    "report this company": 1.0,
    "fraud": 1.0,
    "scam": 1.0,
}

# ---------------------------------------------------------------------------
# Repeat-contact evidence
# ---------------------------------------------------------------------------

REPEAT_MARKERS: Final[tuple[str, ...]] = (
    "third time", "fourth time", "fifth time", "every time",
    "keeps happening", "keep getting", "again and again",
    "not the first time", "multiple times", "several times",
    "same issue", "same problem", "still waiting", "still no",
    "no one has", "yet to receive", "again",
)

# Regex markers supplement the plain-word list (e.g. "3rd time").
REPEAT_REGEXES: Final[tuple[str, ...]] = (
    r"\b\d+(?:st|nd|rd|th)\s+time\b",
    r"\bcontacted\s+(?:you\s+)?\d+\s+times\b",
)

# ---------------------------------------------------------------------------
# Scoring weights and thresholds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoringConfig:
    """Tunable weights and thresholds for the heuristic scorer.

    All confidence-like outputs are bounded to [0, 1].  Values are
    heuristic and were chosen for transparent, testable behaviour; they
    are not fitted to a labelled dataset.
    """

    # Confidence formula: support / (support + prior) * support / (support + opposing)
    confidence_prior: float = 1.0

    # Sentiment: evidence ratio (min/max) at or above which a message with
    # both polarities is called "mixed" instead of the stronger label.
    mixed_sentiment_ratio: float = 0.6

    # Saturation half-lives for raw evidence counts.
    negative_saturation_half: float = 2.0
    cue_saturation_half: float = 1.5
    urgency_saturation_half: float = 1.0

    # Low-confidence fallbacks when no keyword evidence exists.
    general_inquiry_fallback_confidence: float = 0.30
    other_fallback_confidence: float = 0.20
    neutral_fallback_confidence: float = 0.50

    # Frustration composition: weights sum to 1.0 for the positive terms.
    frustration_weight_negative: float = 0.40
    frustration_weight_cues: float = 0.25
    frustration_weight_format: float = 0.15
    frustration_weight_repeat: float = 0.20
    frustration_positive_relief: float = 0.25

    # Escalation risk composition.  Note: frustration (0.35) + urgency
    # (0.10) alone cap at 0.45, below the review threshold, so negative
    # sentiment alone can NEVER trigger human review; explicit escalation
    # language or repeat-contact evidence is always required.
    risk_weight_frustration: float = 0.35
    risk_weight_trigger: float = 0.50
    risk_weight_repeat: float = 0.35
    risk_weight_urgency: float = 0.10
    human_review_risk_threshold: float = 0.50

    # Repeat-contact signal: min(1.0, evidence_count / 2.0).
    repeat_evidence_for_full_signal: float = 2.0

    # Sentiment trend: requires >= min_history_for_trend prior customer
    # messages; delta at or above trend_epsilon is a change of direction.
    min_history_for_trend: int = 2
    trend_epsilon: float = 0.15
    history_window: int = 10

    # Long inputs are truncated to max_analysis_chars before scoring.
    max_analysis_chars: int = 4000

    # Intent keyword weights: multi-word phrases count for more.
    intent_phrase_weight: float = 2.0
    intent_word_weight: float = 1.0

    def __post_init__(self) -> None:
        """Reject nonsensical configurations with a clear message."""
        unit_intervals = {
            "confidence_prior": self.confidence_prior,
            "mixed_sentiment_ratio": self.mixed_sentiment_ratio,
            "human_review_risk_threshold": self.human_review_risk_threshold,
            "trend_epsilon": self.trend_epsilon,
        }
        for name, value in unit_intervals.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0; got {value!r}.")

        if self.max_analysis_chars < 1:
            raise ValueError(
                f"max_analysis_chars must be a positive integer; got {self.max_analysis_chars!r}."
            )
        if self.min_history_for_trend < 1:
            raise ValueError(
                f"min_history_for_trend must be at least 1; got {self.min_history_for_trend!r}."
            )
        if self.history_window < 1:
            raise ValueError(
                f"history_window must be at least 1; got {self.history_window!r}."
            )
        if self.negative_saturation_half <= 0 or self.cue_saturation_half <= 0 or self.urgency_saturation_half <= 0:
            raise ValueError("Saturation half-life values must be greater than zero.")
        if self.repeat_evidence_for_full_signal <= 0:
            raise ValueError("repeat_evidence_for_full_signal must be greater than zero.")


DEFAULT_SCORING_CONFIG: Final[ScoringConfig] = ScoringConfig()

# ---------------------------------------------------------------------------
# Lexicon compilation helpers
# ---------------------------------------------------------------------------


def compile_term(term: str) -> re.Pattern[str]:
    """Compile one lexicon term into a case-insensitive word-bounded regex.

    Whitespace inside multi-word phrases matches any run of whitespace in
    the message, so "can't log in" also matches "can't  LOG  in".
    """
    escaped = r"\s+".join(re.escape(part) for part in term.split())
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


def compile_lexicon(terms: dict[str, float] | tuple[str, ...]) -> list[tuple[re.Pattern[str], float]]:
    """Compile a lexicon into (pattern, weight) pairs, longest term first.

    Sorting longest-first lets phrase matches consume their span before
    overlapping single-word matches are considered.
    """
    if isinstance(terms, dict):
        items = sorted(terms.items(), key=lambda kv: len(kv[0]), reverse=True)
    else:
        items = sorted(((term, 1.0) for term in terms), key=lambda kv: len(kv[0]), reverse=True)
    return [(compile_term(term), weight) for term, weight in items]
