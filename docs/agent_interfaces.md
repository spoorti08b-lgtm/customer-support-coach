# Milestone 2 Agent Interfaces

These contracts define the shared input and output structures for the Customer Simulator,
Sentiment Analysis, and Knowledge Recommendation agents.

## Customer Simulator Agent

**Input:** `SimulatorInput`

- `session_id`: non-empty session identifier
- `persona`: customer persona description
- `history`: previous conversation messages
- `turn_number`: current 1-based turn
- `max_turns`: maximum allowed turns

**Output:** `SimulatorOutput`

- `message`: a `CustomerMessage` containing the generated customer text and turn number
- `is_final`: whether the simulator considers the conversation complete

## Intent and Sentiment Analysis Agent

**Input:** `CustomerMessage`

- `content`: non-empty customer message
- `turn_number`: current 1-based turn
- `metadata`: optional message metadata

**Output:** `SentimentResult`

- `sentiment`: `positive`, `neutral`, `negative`, or `mixed`
- `confidence`: value from 0.0 to 1.0
- `intent`: optional intent label
- `intent_confidence`: optional value from 0.0 to 1.0

## Knowledge Recommendation Agent

**Input:** existing `KnowledgeRecommendationRequest` from
`backend.orchestrator.knowledge_schemas`.

**Output:** existing `KnowledgeRecommendationResponse` from the same module.

It supports `success`, `no_match`, and `error` outcomes. Use its existing
validation and `to_agent_result()` conversion rather than creating a duplicate
knowledge result model.

## Combined turn result

`TurnResult` contains the session ID, turn number, customer message, optional
sentiment and knowledge results, status (`completed`, `partial`, or `failed`),
and a list of `AgentError` values.

## Error contract

`AgentError` contains:

- `agent_name`: agent that encountered the issue
- `code`: stable error code
- `message`: readable error description
- `retryable`: whether retrying may help
- `details`: optional structured diagnostic information

## Orchestrator compatibility

The existing orchestrator expects the shared `AgentResult` dataclass.
Agent implementations should return their typed Pydantic output to their caller;
the integration layer should convert it to `AgentResult` using the existing
conversion method or an adapter before passing it to the orchestrator.

## Validation expectations

- Required text fields must not be empty or whitespace-only where applicable.
- Turn numbers and limits must be positive.
- Confidence values must be between 0.0 and 1.0.
- Agent output must use the documented status and sentiment values.
- Validation errors should be caught at the agent boundary and reported using
  `AgentError`; do not treat schema validation as proof that an AI prediction is correct.

## Validation and error handling

- Validate agent inputs and outputs with the shared Pydantic contracts.
- Invalid required fields, blank messages, invalid turn numbers, unsupported sentiment labels, and confidence values outside 0–1 raise `ValidationError`.
- Catch validation errors at the agent or orchestration boundary and return a consistent `AgentError` rather than allowing an unhandled exception to stop the workflow.
- `AgentError` contains `agent_name`, `code`, `message`, `retryable`, and optional `details`.
- Set `retryable=True` only when retrying may reasonably succeed. Keep diagnostic details safe.
- Pydantic validates structure and constraints; it does not guarantee that an agent’s analysis is factually correct.

## Validation tests

Run the shared contract and validation tests with:

```bash
python -m pytest backend/tests/test_data_models.py backend/tests/test_agent_contract_validation.py -q
```
