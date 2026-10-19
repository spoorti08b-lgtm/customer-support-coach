
# Shared Data Model and Validation Contract

**Project:** AI Customer Support Coaching Assistant  
**Internship:** Infosys Springboard Virtual Internship 7.0  
**Developed by:** Vikas M  
**Module:** Data Model and Validation

## 1. Purpose

This document defines the shared data structures and validation
rules for the Customer Support Coaching Assistant.

The models support the Session Manager, Mock Agent, Orchestrator,
and other agent components.

## 2. Session Model

| Field | Type | Validation |
|---|---|---|
| session_id | String | Required; valid identifier |
| mode | Enum | simulator, manual, replay |
| product_context | Dictionary | JSON-serializable |
| scenario | String, dictionary, or None | Required in simulator mode |
| customer_persona | String, dictionary, or None | Optional |
| status | Enum | active, completed, cancelled |
| created_at | Datetime | Timezone-aware |
| updated_at | Datetime | Timezone-aware; not earlier than creation |
| metadata | Dictionary | JSON-serializable |

## 3. ConversationMessage Model

| Field | Type | Validation |
|---|---|---|
| message_id | String | Required; valid identifier |
| session_id | String | Required; valid identifier |
| speaker | Enum | customer, agent, system |
| content | String | Must not be empty |
| turn_number | Integer | Positive integer |
| timestamp | Datetime | Timezone-aware |
| metadata | Dictionary | JSON-serializable |

## 4. AgentResult Model

| Field | Type | Validation |
|---|---|---|
| result_id | String | Required; valid identifier |
| session_id | String | Required; valid identifier |
| message_id | String or None | Optional valid identifier |
| agent_type | String | Must not be empty |
| result | Dictionary | JSON-serializable |
| created_at | Datetime | Timezone-aware |

## 5. Validation Rules

1. Required text values cannot be empty.
2. IDs must use permitted characters and be 1–128 characters long.
3. Enum values must be supported.
4. Timestamps must include a timezone.
5. Updated time cannot precede creation time.
6. Simulator sessions require a scenario.
7. Message turn numbers must be positive integers.
8. Agent results must be JSON-serializable dictionaries.

## 6. Serialization

Each model provides a `to_dict()` method that returns
JSON-compatible data.

## 7. Integration Responsibilities

- The Session Manager handles session persistence and retrieval.
- The persistence layer must enforce ID uniqueness and validate references.
- Replay mode should preserve the original conversation order.
- The team should confirm shared field names before integration.

## 8. Tests

Automated unit tests are provided in `tests/test_data_models.py`.
The current test file contains 12 tests covering valid and invalid
inputs, validation rules, and serialization.
