# Intent, Emotion, Frustration, Sentiment Tracking and Context Hand-off

This document describes the extended output of the Intent and Sentiment
Analysis Agent (`backend/agents/intent_sentiment_agent.py`) added for:

1. Customer intent identification
2. Emotion detection (anger, frustration, confusion, happiness, satisfaction, ...)
3. Frustration level
4. Sentiment tracking across conversation turns
5. Context from previous customer messages
6. Structured output for the Knowledge, Escalation and Coaching agents

## Method note

Classification remains **rule-based**: transparent keyword lexicons,
weighted evidence scoring, and hand-tuned thresholds in
`backend/agents/intent_sentiment_config.py`. It is **not** a trained model,
and every `confidence` value is a heuristic evidence share, not a calibrated
probability. Everything runs locally on CPU with no network access.

## Output contract

`IntentSentimentResult` extends the shared Milestone 2 `SentimentResult`:

| Field | Type | Meaning |
| --- | --- | --- |
| `sentiment` | `positive` / `neutral` / `negative` / `mixed` | Current message sentiment |
| `confidence` | `0.0`–`1.0` | Heuristic sentiment confidence |
| `intent` | `str` | Detected intent label |
| `intent_confidence` | `0.0`–`1.0` | Heuristic intent confidence |
| `emotion` | `list[str]` | Emotion indicators (a message may show several) |
| `frustration_score` | `0.0`–`1.0` | Continuous frustration estimate |
| `frustration_level` | `none` / `low` / `moderate` / `high` / `severe` | Banded from the score |
| `escalation_risk_score` | `0.0`–`1.0` | Heuristic escalation risk |
| `requires_human_review` | `bool` | Risk reached the review threshold |
| `explanation` | `str` | Short, content-free risk explanation |
| `sentiment_trend` | `improving` / `stable` / `worsening` / `unknown` | Direction across customer turns |
| `sentiment_trajectory` | `list[SentimentTrajectoryPoint]` | Per-turn sentiment points |
| `conversation_context` | `ConversationContext` | Summary of prior customer turns |
| `turn_number` | `int` | Current 1-indexed turn |
| `handoff` | `AgentHandoff` | Payloads for the three downstream agents |

`handoff` is populated by `analyze()`; it is `None` only for hand-built
results. The new fields have defaults, so existing callers that construct
`IntentSentimentResult` directly keep working.

## Emotions

Labels come from `EMOTION_INDICATORS`: `frustration`, `anger`, `confusion`,
`disappointment`, `satisfaction`, `happiness`, `urgency`. When nothing
matches, the list is `["neutral"]`.

## Frustration levels

Levels are derived from `frustration_score` with strictly increasing
thresholds in `ScoringConfig` (`0.20`, `0.40`, `0.60`, `0.80` by default):

| Score | Level |
| --- | --- |
| `< 0.20` | `none` |
| `0.20 – 0.39` | `low` |
| `0.40 – 0.59` | `moderate` |
| `0.60 – 0.79` | `high` |
| `>= 0.80` | `severe` |

Because the label is banded from the reported score, the two never disagree.

## Sentiment tracking

`sentiment_trajectory` records one point per customer turn in the analysis
window, oldest first, ending with the current message:

```json
[
  {"turn_number": 1, "sentiment": "neutral",  "polarity": 0.0,  "emotions": ["neutral"],     "frustration_score": 0.0},
  {"turn_number": 3, "sentiment": "negative", "polarity": -1.0, "emotions": ["frustration"], "frustration_score": 0.2762}
]
```

Agent turns are ignored. `max_trajectory_points` (default 12) keeps only the
most recent customer turns. `sentiment_trend` is still computed from the
polarities of prior customer turns and stays `unknown` until
`min_history_for_trend` prior messages exist.

## Conversation context

`ConversationContext` summarises what the agent used from earlier turns:

```json
{
  "has_context": true,
  "customer_turns": 2,
  "window_start_turn": 1,
  "window_end_turn": 3,
  "prior_intents": ["billing_or_payment", "technical_issue"],
  "dominant_intent": "billing_or_payment",
  "unresolved_turns": 1,
  "recurring_issue": true,
  "average_prior_frustration": 0.1381,
  "prior_emotion_counts": {"neutral": 1, "frustration": 1}
}
```

The context stores labels, scores, and counts only — **never raw customer
message text** — so it is safe to log and persist. `recurring_issue` is true
when the current intent was already classified for an earlier customer turn,
and it feeds both repeat-contact evidence and the coaching focus areas.

History is read from `session.metadata["conversation_history"]` (or
`"history"`), falling back to `session.replay_transcript`, in
`IntentSentimentAgent.run(session, message)`.

## Hand-off payloads

`AgentHandoff` carries one typed payload per consumer
(`backend/agents/agent_handoff.py`):

| Payload | Consumer | Contents |
| --- | --- | --- |
| `KnowledgeHandoff` | Knowledge Recommendation Agent | `intent`, `intent_confidence`, `suggested_query`, `sentiment`, `emotions`, `turn_number`, `customer_turns_of_context`, `recurring_issue` |
| `EscalationHandoff` | Escalation Agent | `priority`, `requires_human_review`, `escalation_risk_score`, `frustration_level`, `sentiment_trend`, `signals`, `recommended_action` |
| `CoachingHandoff` | Coaching Agent | `focus_areas`, `sentiment`, `sentiment_trend`, `frustration_level`, `dominant_emotion`, `guidance` |

Routing rules:

- `p1_critical`: risk `>= critical_risk_threshold` (0.80) or `severe`
  frustration.
- `p2_high`: `requires_human_review` is true.
- `p3_medium`: `high` frustration or a `worsening` trend.
- `p4_low`: everything else.

Signals are machine-readable (`legal_or_public_threat`,
`explicit_escalation_request`, `repeated_contact`, `high_frustration`,
`negative_sentiment`, `worsening_trend`, `time_pressure`), falling back to
`no_escalation_signals`.

Coaching focus areas include `empathy_and_ownership`, `de_escalation`,
`clarify_and_confirm`, `expectation_management`, `reinforce_and_close`,
`time_commitment`, plus `sentiment_recovery` for a worsening trend and
`context_continuity` for recurring issues.

The knowledge `suggested_query` is derived from the intent label only
(`"billing_or_payment customer support policy"`); the orchestrator still
holds the message and passes it to the Knowledge Agent separately.

## Usage

```python
from backend.agents import analyze_message

result = analyze_message(
    "Payment failed again, I am confused and angry!",
    [
        {"speaker": "customer", "content": "My payment failed.", "turn_number": 1},
        {"speaker": "agent", "content": "Let me check.", "turn_number": 2},
    ],
)

result.intent                # "billing_or_payment"
result.frustration_level     # "moderate"
result.sentiment_trend       # "worsening"
result.handoff.escalation.priority
result.handoff.coaching.focus_areas
```

## Tests

```bash
python -m pytest backend/tests/test_intent_sentiment_agent.py \
                 backend/tests/test_intent_emotion_context.py -q
```
