"""Agent implementations package.

Contains agent implementations for the Customer Support Coach platform,
including the Knowledge Recommendation Agent, the Intent and Sentiment
Analysis Agent, and dialogue agents.

``KnowledgeRecommendationAgent`` is resolved lazily through PEP 562
module ``__getattr__`` because it depends on the optional RAG stack
(chromadb, pypdf, sentence-transformers, streamlit).  The public API is
unchanged — ``from backend.agents import KnowledgeRecommendationAgent``
still works whenever those dependencies are importable, and the original
import error (with its cause chained) is raised at that access point if
they are not.  This keeps the lightweight Intent and Sentiment Analysis
Agent importable in minimal, CPU-only environments.
"""

from __future__ import annotations

from typing import Any

from backend.agents.intent_sentiment_agent import (
    IntentSentimentAgent,
    IntentSentimentResult,
    analyze_message,
)

__all__ = [
    "IntentSentimentAgent",
    "IntentSentimentResult",
    "KnowledgeRecommendationAgent",
    "analyze_message",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve the RAG-backed knowledge agent on first access."""
    if name == "KnowledgeRecommendationAgent":
        from backend.agents.knowledge_agent import KnowledgeRecommendationAgent

        globals()[name] = KnowledgeRecommendationAgent
        return KnowledgeRecommendationAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
