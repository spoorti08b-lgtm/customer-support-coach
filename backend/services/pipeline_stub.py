"""Rule-based stand-ins for agents so the UI can run without live agents.

Team integration: replace these functions with real agents while keeping
the returned dictionary keys consistent.
"""

from backend.services import rag_stub


NEG = [
    "angry", "ridiculous", "unacceptable", "worst", "terrible", "furious",
    "useless", "still", "again", "waiting", "never", "not working",
    "broken", "cancel", "lawyer", "complaint", "!!",
]
POS = [
    "thanks", "thank you", "great", "perfect", "appreciate", "resolved",
    "works", "happy", "helpful",
]
INTENTS = {
    "Refund / billing": ["refund", "charge", "billing", "invoice", "payment", "money"],
    "Cancellation": ["cancel", "close my account", "unsubscribe"],
    "Technical issue": ["error", "not working", "broken", "crash", "login", "bug", "app"],
    "Delivery / order": ["delivery", "order", "shipping", "package", "tracking"],
    "Account access": ["password", "account", "locked", "access"],
}

LADDERS = {
    "Calm": [
        "Hi, I need help with {p}. {s}",
        "Okay, I tried that but it's still the same. Could you check again?",
        "Alright, thanks. How long will this take?",
        "I see. Is there anything else I can try on my side?",
        "Great, that works now. Thank you!",
    ],
    "Impatient": [
        "Hello, {p} is giving me trouble. {s} I need this fixed fast.",
        "That's not helpful, I've already tried that. Can we move quicker?",
        "I'm still waiting for a real answer. This is taking too long!",
        "Honestly this is unacceptable. I need a solution right now.",
        "Fine. If it works, I'll be done with this.",
    ],
    "Angry": [
        "This is ridiculous! {s} {p} has been terrible!!",
        "I've contacted you again and nothing is fixed. This is the worst service!",
        "I want a refund and I'm ready to cancel. Get me a manager!",
        "You keep repeating yourselves. I'm furious and will file a complaint.",
        "Okay... fine. Just fix it and I may reconsider.",
    ],
    "Confused": [
        "Hi, I'm not sure what's happening with {p}. {s}",
        "Sorry, I don't understand what you mean. Where do I find that?",
        "I'm confused, can you explain step by step?",
        "Okay, I tried it but I'm not sure it worked. Did it?",
        "Oh I see now, thank you so much for explaining.",
    ],
}


def simulate_customer(cfg, turn):
    """Return a simulated customer message for the selected persona."""
    ladder = LADDERS.get(cfg.get("persona", "Calm"), LADDERS["Calm"])
    message_index = min(turn, len(ladder) - 1)
    return ladder[message_index].format(
        p=cfg.get("product", "your product"),
        s=cfg.get("scenario", ""),
    )


def analyze_turn(text, history, cfg):
    """Analyze intent, sentiment, escalation risk, coaching, and knowledge."""
    t = text.lower()
    neg = sum(word in t for word in NEG)
    pos = sum(word in t for word in POS)
    n_cust = sum(message["role"] == "customer" for message in history)

    frustration = max(
        0,
        min(
            100,
            20 + neg * 18 - pos * 20
            + (10 if t.count("!") >= 2 else 0)
            + n_cust * 4,
        ),
    )
    emotion = (
        "Angry" if frustration >= 75
        else "Frustrated" if frustration >= 50
        else "Satisfied" if frustration <= 20
        else "Neutral"
    )
    sentiment = {
        "Angry": "Negative",
        "Frustrated": "Negative",
        "Neutral": "Neutral",
        "Satisfied": "Positive",
    }[emotion]
    intent = next(
        (name for name, words in INTENTS.items() if any(word in t for word in words)),
        "General inquiry",
    )
    risk = max(0, min(100, int(frustration * 0.8 + neg * 6)))

    reasons = []
    if neg:
        reasons.append(f"{neg} negative cue(s) in the message")
    if n_cust >= 3 and frustration >= 50:
        reasons.append("customer has contacted repeatedly")
    if any(word in t for word in ("cancel", "refund", "manager")):
        reasons.append("explicit churn/escalation request")

    opener = {
        "Angry": "I completely understand how frustrating this is, and I'm sorry. ",
        "Frustrated": "I'm sorry for the trouble — let's sort this out together. ",
        "Neutral": "Thanks for the details. ",
        "Satisfied": "Glad to hear that! ",
    }[emotion]

    return {
        "intent": intent,
        "emotion": emotion,
        "sentiment": sentiment,
        "frustration": frustration,
        "risk": risk,
        "risk_reason": "; ".join(reasons) or "No strong escalation signals.",
        "strategy": (
            "Acknowledge, own the issue, offer a concrete next step and timeline; "
            "offer a supervisor if asked."
        ) if risk >= 70 else "Keep resolving; confirm understanding.",
        "suggestion": (
            f"{opener}Regarding your {intent.lower()}, here's what I'll do next: "
            "[use the knowledge panel steps]. Does that work for you?"
        ),
        "chunks": rag_stub.retrieve(text, k=3),
    }


def evaluate_agent_reply(text):
    """Give a simple coaching score and feedback for an agent reply."""
    words = len(text.split())
    empathy = any(
        word in text.lower() for word in ("sorry", "understand", "apolog", "thank")
    )
    shouty = text.isupper() or text.count("!") > 2
    notes = [
        "✅ Empathetic tone" if empathy
        else "⚠️ Add an empathy phrase (e.g. 'I understand...')",
        "✅ Clear length" if 8 <= words <= 80
        else "⚠️ Aim for 8–80 words for clarity",
        "⚠️ Avoid ALL CAPS / excess '!'" if shouty
        else "✅ Calm formatting",
    ]
    score = 40 + 20 * empathy + 20 * (8 <= words <= 80) + 20 * (not shouty)
    return {"score": score, "notes": notes}


SAMPLE_TRANSCRIPT = """Customer: Hi, my refund for order #4521 still hasn't arrived after 10 days.
Agent: Hello! I'm sorry about the delay. Let me check the status for you.
Customer: This is the third time I'm contacting you. It's ridiculous!
Agent: I understand your frustration. I can see the refund was initiated on the 3rd and is pending at the bank.
Customer: I don't care about the bank. I want my money back or I'll cancel my account.
Agent: I'm escalating this now and will email you a confirmation within 24 hours.
Customer: Okay, thanks. Please make sure it actually happens this time.
"""
