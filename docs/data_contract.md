
# Shared Data Model and Validation Contract

**Project:** AI Customer Support Coaching Assistant  
**Internship:** Infosys Springboard Virtual Internship 7.0  
**Developed by:** Vikas M  
**Module:** Data Model and Validation

## 1. Purpose

This document defines the shared data structures and validation rules for the Customer Support Coaching Assistant.

The models provide a common data contract for the Session Manager, Mock Agent, Orchestrator, and other agent components. They help maintain consistent data formats across the application.

## 2. Session Model

The `Session` model represents one customer-support training session.

| Field | Type | Validation |
|---|---|---|
| `session_id` | String | Required; 1–128 permitted identifier characters |
| `mode` | Enum | `simulator`, `manual`, or `replay` |
| `product_context` | Dictionary | Must contain strict JSON-compatible data |
| `scenario` | String, dictionary, or `None` | Required in simulator mode |
| `customer_persona` | String, dictionary, or `None` | Optional; validated when provided |
| `status` | Enum | `active`, `completed`, or `cancelled` |
| `created_at` | Datetime | Must be timezone-aware |
| `updated_at` | Datetime | Must be timezone-aware and not earlier than creation |
| `metadata` | Dictionary | Must contain strict JSON-compatible data |

### Session behavior

- A session ID is generated automatically when one is not supplied.
- The default interaction mode is `simulator`.
- The default session status is `active`.
- Simulator sessions must include a scenario.
- Timestamps are normalized to UTC.
- The `to_dict()` method serializes the session into a dictionary.

## 3. ConversationMessage Model

The `ConversationMessage` model represents one message in a support conversation.

| Field | Type | Validation |
|---|---|---|
| `message_id` | String | Required; valid identifier |
| `session_id` | String | Required; valid identifier |
| `speaker` | Enum | `customer`, `agent`, or `system` |
| `content` | String | Must be non-empty after trimming whitespace |
| `turn_number` | Integer | Must be a positive integer; booleans are rejected |
| `timestamp` | Datetime | Must be timezone-aware |
| `metadata` | Dictionary | Must contain strict JSON-compatible data |

### Conversation message behavior

- A message ID is generated automatically when one is not supplied.
- The timestamp defaults to the current UTC time.
- The speaker is normalized to the supported `Speaker` enum.
- The `to_dict()` method serializes the message and represents the timestamp as an ISO 8601 string.

## 4. AgentResult Model

The `AgentResult` model stores the result produced by an AI agent.

| Field | Type | Validation |
|---|---|---|
| `result_id` | String | Required; valid identifier |
| `session_id` | String | Required; valid identifier |
| `message_id` | String or `None` | Optional; must be a valid identifier when supplied |
| `agent_type` | String | Must be non-empty after trimming whitespace |
| `result` | Dictionary | Must contain strict JSON-compatible data |
| `created_at` | Datetime | Must be timezone-aware |

### Agent result behavior

- A result ID is generated automatically when one is not supplied.
- The creation timestamp defaults to the current UTC time.
- The `to_dict()` method serializes the result into a dictionary.

## 5. Validation Rules

The shared validation helpers enforce the following rules:

1. Required text values must be non-empty.
2. Identifiers must contain 1–128 characters from the permitted set: letters, digits, underscore, period, colon, and hyphen.
3. Enum values must match supported values.
4. Timestamps must be timezone-aware.
5. Timestamps are normalized to UTC.
6. A session's `updated_at` cannot precede its `created_at`.
7. Simulator sessions require a scenario.
8. Message turn numbers must be positive integers.
9. Dictionary fields must contain JSON-serializable data.
10. Non-standard JSON numeric values such as `NaN` and infinity are rejected.
11. Invalid model input raises the custom `ValidationError`, which is a subclass of `ValueError`.

## 6. Serialization

All three models provide a `to_dict()` method.

- `Session.to_dict()` returns session details.
- `ConversationMessage.to_dict()` returns conversation message details.
- `AgentResult.to_dict()` returns agent result details.
- Datetime values are serialized as ISO 8601 strings.
- Enum values are serialized using their string values.

The returned dictionaries are intended for use by application components and JSON-based persistence or communication layers.

## 7. Integration Responsibilities

The shared models define data structures and validation. They do not implement session persistence, agent execution, or orchestration.

- **Session Manager:** Handles session lifecycle, persistence, and retrieval.
- **Persistence layer:** Should enforce ID uniqueness, validate references, and manage storage.
- **Mock Agent:** Should use the agreed conversation message and session data contract.
- **Orchestrator:** Should pass validated data between application components.
- **Replay functionality:** Should preserve the original conversation order and relevant timestamps.
- **Project team:** Should confirm field names, types, and serialization expectations before integrating modules.

Integration with the Mock Agent, Session Manager, and Orchestrator must be verified separately.

## 8. Unit Tests

Automated unit tests are provided in `tests/test_data_models.py`.

The current test suite contains **15 tests** covering:

- Valid session creation
- Required simulator scenarios
- Invalid session IDs and statuses
- Session serialization
- Invalid interaction mode types
- Valid conversation messages
- Empty message content
- Invalid speaker values and types
- Invalid turn numbers
- Valid agent results
- Empty agent types
- Non-JSON-compatible result data
- Rejection of `NaN` in agent results

Run the tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```

**Latest reported result:** 15 tests passed.

## 9. Scope and Limitations

This module provides shared data models, input validation, and serialization. It does not independently guarantee:

- Database persistence or identifier uniqueness
- Referential integrity between sessions, messages, and results
- Compatibility with every agent component
- Correctness of AI-generated outputs
- End-to-end application behavior

These responsibilities require additional implementation and integration testing.
