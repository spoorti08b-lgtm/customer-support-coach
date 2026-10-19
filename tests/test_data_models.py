"""
Unit tests for Data Models and Validation.
Developed by Vikas M
Infosys Springboard Virtual Internship 7.0
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from customer_support_coach.data_models import (
    AgentResult,
    ConversationMessage,
    Session,
    ValidationError,
)


class TestSession(unittest.TestCase):

    def test_valid_session(self):
        session = Session(
            session_id="session-001",
            scenario="delayed_delivery",
        )
        self.assertEqual(session.session_id, "session-001")

    def test_simulator_requires_scenario(self):
        with self.assertRaises(ValidationError):
            Session()

    def test_invalid_session_id(self):
        with self.assertRaises(ValidationError):
            Session(session_id="bad id", scenario="delivery")

    def test_invalid_status(self):
        with self.assertRaises(ValidationError):
            Session(scenario="delivery", status="unknown")

    def test_session_serialization(self):
        session = Session(
            session_id="session-002",
            scenario="billing",
        )
        data = session.to_dict()
        self.assertEqual(data["session_id"], "session-002")
        self.assertEqual(data["mode"], "simulator")


class TestConversationMessage(unittest.TestCase):

    def test_valid_message(self):
        message = ConversationMessage(
            session_id="session-001",
            speaker="customer",
            content="My order is late.",
            turn_number=1,
        )
        self.assertEqual(message.content, "My order is late.")

    def test_empty_message_rejected(self):
        with self.assertRaises(ValidationError):
            ConversationMessage(
                session_id="session-001",
                speaker="customer",
                content=" ",
                turn_number=1,
            )

    def test_invalid_speaker_rejected(self):
        with self.assertRaises(ValidationError):
            ConversationMessage(
                session_id="session-001",
                speaker="unknown",
                content="Hello",
                turn_number=1,
            )

    def test_invalid_turn_rejected(self):
        with self.assertRaises(ValidationError):
            ConversationMessage(
                session_id="session-001",
                speaker="agent",
                content="Hello",
                turn_number=0,
            )


class TestAgentResult(unittest.TestCase):

    def test_valid_agent_result(self):
        result = AgentResult(
            session_id="session-001",
            agent_type="intent_sentiment",
            result={"intent": "refund", "confidence": 0.9},
        )
        self.assertEqual(result.result["intent"], "refund")

    def test_empty_agent_type_rejected(self):
        with self.assertRaises(ValidationError):
            AgentResult(
                session_id="session-001",
                agent_type=" ",
                result={},
            )

    def test_non_json_result_rejected(self):
        with self.assertRaises(ValidationError):
            AgentResult(
                session_id="session-001",
                agent_type="summary",
                result={"bad": object()},
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)