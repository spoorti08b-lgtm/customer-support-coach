
"""Unit tests for shared data models and validation."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from customer_support_coach.data_models import (
    AgentResult,
    ConversationMessage,
    InteractionMode,
    Session,
    SessionStatus,
    Speaker,
    ValidationError,
)


class TestSession(unittest.TestCase):
    def test_valid_session(self):
        session = Session(
            mode=InteractionMode.SIMULATOR,
            scenario="Customer has an order issue",
        )

        self.assertTrue(session.session_id.startswith("sess-"))
        self.assertEqual(session.mode, InteractionMode.SIMULATOR)
        self.assertEqual(session.status, SessionStatus.ACTIVE)
        self.assertEqual(
            session.scenario,
            "Customer has an order issue",
        )

    def test_simulator_requires_scenario(self):
        with self.assertRaises(ValidationError):
            Session(mode=InteractionMode.SIMULATOR)

    def test_invalid_session_id(self):
        with self.assertRaises(ValidationError):
            Session(
                session_id="invalid id!",
                scenario="Order issue",
            )

    def test_invalid_status(self):
        with self.assertRaises(ValidationError):
            Session(
                status="unknown",
                scenario="Order issue",
            )

    def test_session_serialization(self):
        session = Session(
            mode=InteractionMode.MANUAL,
            scenario=None,
        )

        data = session.to_dict()

        self.assertEqual(data["mode"], "manual")
        self.assertEqual(data["status"], "active")
        self.assertIsInstance(data["created_at"], str)
        self.assertIsInstance(data["updated_at"], str)

    def test_invalid_mode_type_rejected(self):
        with self.assertRaises(ValidationError):
            Session(
                mode=[],
                scenario="Order issue",
            )


class TestConversationMessage(unittest.TestCase):
    def test_valid_message(self):
        message = ConversationMessage(
            session_id="sess-123",
            speaker=Speaker.CUSTOMER,
            content="Where is my order?",
            turn_number=1,
        )

        self.assertTrue(message.message_id.startswith("msg-"))
        self.assertEqual(message.speaker, Speaker.CUSTOMER)
        self.assertEqual(message.turn_number, 1)

    def test_empty_message_rejected(self):
        with self.assertRaises(ValidationError):
            ConversationMessage(
                session_id="sess-123",
                speaker="customer",
                content="   ",
                turn_number=1,
            )

    def test_invalid_speaker_rejected(self):
        with self.assertRaises(ValidationError):
            ConversationMessage(
                session_id="sess-123",
                speaker="unknown",
                content="Hello",
                turn_number=1,
            )

    def test_invalid_turn_rejected(self):
        with self.assertRaises(ValidationError):
            ConversationMessage(
                session_id="sess-123",
                speaker="customer",
                content="Hello",
                turn_number=0,
            )

    def test_invalid_speaker_type_rejected(self):
        with self.assertRaises(ValidationError):
            ConversationMessage(
                session_id="sess-123",
                speaker=[],
                content="Hello",
                turn_number=1,
            )


class TestAgentResult(unittest.TestCase):
    def test_valid_agent_result(self):
        result = AgentResult(
            session_id="sess-123",
            agent_type="sentiment",
            result={"sentiment": "positive", "score": 0.95},
        )

        self.assertTrue(result.result_id.startswith("res-"))
        self.assertEqual(result.agent_type, "sentiment")
        self.assertEqual(result.result["sentiment"], "positive")

    def test_empty_agent_type_rejected(self):
        with self.assertRaises(ValidationError):
            AgentResult(
                session_id="sess-123",
                agent_type="",
                result={},
            )

    def test_non_json_result_rejected(self):
        with self.assertRaises(ValidationError):
            AgentResult(
                session_id="sess-123",
                agent_type="sentiment",
                result={"value": object()},
            )

    def test_nan_result_rejected(self):
        with self.assertRaises(ValidationError):
            AgentResult(
                session_id="sess-123",
                agent_type="sentiment",
                result={"score": float("nan")},
            )


if __name__ == "__main__":
    unittest.main()
