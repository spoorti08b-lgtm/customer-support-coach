
"""
Intent and Sentiment Analysis Agent - demonstration script.

Run from the project root:

    python demo_intent_sentiment.py

Shows five scenarios:
  1. Sentiment and emotion on positive / neutral / negative messages
  2. Intent classification across every default category
  3. Frustration, escalation risk, and the human-review flag
  4. Conversation history: sentiment trend and recurring issues
  5. Invalid input handling and orchestrator integration

Everything runs locally on CPU: no API keys, network calls, or model
downloads. The agent is rule-based; see docs/intent_sentiment_agent.md.
"""

from __future__ import annotations

from pydantic import ValidationError

from backend.agents.intent_sentiment_agent import (
    IntentSentimentAgent,
    analyze_message,
)
from backend.core.data_models import Session


def heading(title: str) -> None:
    """Print a scenario heading."""
    print(f"\n{'=' * 72}\n  {title}\n{'=' * 72}")


def show(
    label: str,
    message: str,
    history: list | None = None,
) -> None:
    """Analyse one message and print the key result fields."""
    result = analyze_message(
        message,
        conversation_history=history,
    )

    print(f"\n  [{label}] {message!r}")
    print(
        f"    intent        : {result.intent} "
        f"(confidence {result.intent_confidence})"
    )
    print(
        f"    sentiment     : {result.sentiment} "
        f"(confidence {result.confidence})"
    )
    print(f"    emotions      : {', '.join(result.emotion)}")
    print(
        f"    frustration   : {result.frustration_score:.2f} | "
        f"escalation risk: {result.escalation_risk_score:.2f} | "
        f"human review: {result.requires_human_review}"
    )
    print(f"    trend         : {result.sentiment_trend}")
    print(f"    explanation   : {result.explanation}")


def show_validation_error(message: object) -> None:
    """Run invalid input through the public API and display validation errors."""
    try:
        analyze_message(message)
    except ValidationError as exc:
        errors = exc.errors()

        if errors:
            first = errors[0]
            print(
                f"  input={message!r:8} -> "
                f"ValidationError: {first['msg']}"
            )
        else:
            print(f"  input={message!r:8} -> ValidationError")
    except (TypeError, ValueError) as exc:
        # Some invalid inputs may be rejected by explicit Python validation
        # rather than by Pydantic. Display those errors without hiding them.
        print(
            f"  input={message!r:8} -> "
            f"{type(exc).__name__}: {exc}"
        )
    else:
        print(
            f"  input={message!r:8} -> "
            "WARNING: input was accepted"
        )


def main() -> None:
    """Run all demonstration scenarios."""

    # Scenario 1: sentiment and emotion
    heading("Scenario 1 - Sentiment and emotion detection")

    show(
        "positive",
        "Thank you so much! The issue is fixed and I am happy.",
    )
    show(
        "neutral",
        "Your package contains three items and the invoice is enclosed.",
    )
    show(
        "negative",
        "The product is broken and the delivery was late.",
    )

    # Scenario 2: intent categories
    heading("Scenario 2 - Intent classification (default labels)")

    samples = {
        "billing_or_payment": (
            "I was charged twice for the same payment."
        ),
        "technical_issue": (
            "The app crashes with an error every time I open it."
        ),
        "account_access": (
            "I am locked out and cannot reset my password."
        ),
        "refund_or_cancellation": (
            "I want a refund and to cancel my subscription."
        ),
        "order_or_service_status": (
            "Where is my order? The tracking has not updated."
        ),
        "product_information": (
            "What are the specs and is this model compatible?"
        ),
        "complaint": (
            "I would like to file a formal complaint about your service."
        ),
        "general_inquiry": (
            "Hello, could you tell me how do I contact support?"
        ),
        "other": "ok",
    }

    for expected, text in samples.items():
        result = analyze_message(text)
        mark = "OK " if result.intent == expected else "!! "

        print(
            f"  {mark}{expected:24s} -> "
            f"{result.intent:24s} "
            f"(confidence {result.intent_confidence})"
        )

    # Scenario 3: frustration, escalation, human review
    heading("Scenario 3 - Frustration, escalation, human review")

    show(
        "calm question",
        "Could you tell me when the store opens on weekdays?",
    )
    show(
        "angry but no trigger",
        "This is terrible, awful, horrible and useless!!!",
    )
    show(
        "repeated contact",
        "Third time contacting you and still no response!!!",
    )
    show(
        "escalation request",
        "This is unacceptable, I want a manager right now!!",
    )
    show(
        "legal threat",
        "I will sue you and dispute the charge with my bank today.",
    )

    print(
        "\n  Note: negative sentiment alone should not automatically "
        "set requires_human_review.\n"
        "  Verify the agent's escalation policy against the project "
        "requirements."
    )

    # Scenario 4: conversation history
    heading("Scenario 4 - Conversation history and sentiment trend")

    worsening_history = [
        {
            "speaker": "customer",
            "content": "Thanks for the quick help!",
        },
        {
            "speaker": "customer",
            "content": "Great, all good now.",
        },
    ]

    show(
        "no history",
        "Still waiting, nothing works and no one replies!!!",
    )

    show(
        "positive history",
        "Still waiting, nothing works and no one replies!!!",
        history=worsening_history,
    )

    recurring_history = [
        {
            "speaker": "customer",
            "content": "My payment failed.",
        },
        {
            "speaker": "customer",
            "content": "Payment failed again.",
        },
    ]

    show(
        "recurring issue",
        "The payment is still failing after your last fix.",
        history=recurring_history,
    )

    # Scenario 5: invalid input handling
    heading("Scenario 5 - Invalid input handling")

    for bad in ("", "   ", None):
        show_validation_error(bad)

    # Scenario 5b: orchestrator integration
    heading("Scenario 5b - Orchestrator integration (agent.run)")

    agent = IntentSentimentAgent()

    session = Session(
        session_id="sess-demo01",
        mode="Manual",
        scenario=None,
    )

    result = agent.run(
        session=session,
        message="My payment failed again, please help!",
    )

    print(f"  agent_type : {result.agent_type}")
    print(f"  session_id : {result.session_id}")

    if isinstance(result.result, dict):
        print(
            f"  payload    : "
            f"intent={result.result.get('intent')!r}, "
            f"risk={result.result.get('escalation_risk_score')}"
        )
    else:
        print(f"  payload    : {result.result!r}")

    failed = agent.run(
        session=session,
        message="   ",
    )

    if (
        isinstance(failed.result, dict)
        and failed.result.get("errors")
    ):
        error = failed.result["errors"][0]
        print(
            f"  invalid input payload -> "
            f"status={failed.result.get('status')!r}, "
            f"code={error.get('code')!r}, "
            f"retryable={error.get('retryable')}"
        )
    else:
        print(
            "  invalid input payload -> "
            f"{failed.result!r}"
        )

    print(f"\n{'=' * 72}\n  Demo complete.\n{'=' * 72}\n")


if __name__ == "__main__":
    main()
