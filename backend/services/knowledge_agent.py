"""Knowledge Recommendation Agent implementation.

Re-exports KnowledgeRecommendationAgent from backend.agents.knowledge_agent
for backward compatibility across existing services and tests.
"""

from backend.agents.knowledge_agent import (
    DOMAINS,
    MAX_CLUE_CHARS,
    MAX_QUERY_CHARS,
    PRONOUN_REF_WORDS,
    STOP_WORDS,
    KnowledgeRecommendationAgent,
    _extract_salient_clue,
    _get_text_domains,
    _is_relevant_turn,
)

__all__ = [
    "DOMAINS",
    "MAX_CLUE_CHARS",
    "MAX_QUERY_CHARS",
    "PRONOUN_REF_WORDS",
    "STOP_WORDS",
    "KnowledgeRecommendationAgent",
    "_extract_salient_clue",
    "_get_text_domains",
    "_is_relevant_turn",
]
