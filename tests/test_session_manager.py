
import tempfile
import unittest
from pathlib import Path

from customer_support_coach.data_models import (
    Session,
    InteractionMode,
    SessionStatus,
    ConversationMessage,
    Speaker,
    AgentResult,
)
from customer_support_coach.session_manager import SessionManager


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.manager = SessionManager(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_get_session(self):
        session = Session(
            mode=InteractionMode.SIMULATOR,
            scenario={"issue": "order delay"},
        )
        self.manager.create_session(session)

        retrieved = self.manager.get_session(session.session_id)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.session_id, session.session_id)
        self.assertEqual(retrieved.mode, InteractionMode.SIMULATOR)
        self.assertEqual(retrieved.scenario, {"issue": "order delay"})

    def test_missing_session_returns_none(self):
        self.assertIsNone(self.manager.get_session("sess-does-not-exist"))

    def test_add_and_get_message(self):
        session = Session(
            mode=InteractionMode.SIMULATOR,
            scenario={"issue": "order delay"},
        )
        self.manager.create_session(session)

        message = ConversationMessage(
            session_id=session.session_id,
            speaker=Speaker.CUSTOMER,
            content="Where is my order?",
            turn_number=1,
        )
        self.manager.add_message(message)

        messages = self.manager.get_messages(session.session_id)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].content, "Where is my order?")

    def test_save_and_get_agent_result(self):
        session = Session(
            mode=InteractionMode.SIMULATOR,
            scenario={"issue": "order delay"},
        )
        self.manager.create_session(session)

        result = AgentResult(
            session_id=session.session_id,
            agent_type="sentiment",
            result={"sentiment": "positive", "confidence": 0.95},
        )
        self.manager.save_agent_result(result)

        results = self.manager.get_agent_results(session.session_id)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].result["sentiment"], "positive")

    def test_update_session_status(self):
        session = Session(
            mode=InteractionMode.SIMULATOR,
            scenario={"issue": "order delay"},
        )
        self.manager.create_session(session)

        updated = self.manager.update_session_status(
            session.session_id,
            SessionStatus.COMPLETED,
        )

        self.assertTrue(updated)
        self.assertEqual(
            self.manager.get_session(session.session_id).status,
            SessionStatus.COMPLETED,
        )

    def test_list_sessions(self):
        first = Session(
            mode=InteractionMode.SIMULATOR,
            scenario={"issue": "first"},
        )
        second = Session(
            mode=InteractionMode.SIMULATOR,
            scenario={"issue": "second"},
        )
        self.manager.create_session(first)
        self.manager.create_session(second)

        sessions = self.manager.list_sessions()

        self.assertEqual(len(sessions), 2)
        self.assertEqual(
            {s.session_id for s in sessions},
            {first.session_id, second.session_id},
        )

    def test_message_requires_existing_session(self):
        message = ConversationMessage(
            session_id="sess-missing",
            speaker=Speaker.CUSTOMER,
            content="Hello",
            turn_number=1,
        )

        with self.assertRaises(ValueError):
            self.manager.add_message(message)

    def test_data_survives_new_manager_instance(self):
        session = Session(
            mode=InteractionMode.SIMULATOR,
            scenario={"issue": "order delay"},
        )
        self.manager.create_session(session)

        new_manager = SessionManager(self.db_path)
        retrieved = new_manager.get_session(session.session_id)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.scenario, {"issue": "order delay"})

    def test_replay_messages_are_returned_in_turn_order(self):
        session = Session(mode=InteractionMode.REPLAY)
        self.manager.create_session(session)

        second = ConversationMessage(
            session_id=session.session_id,
            speaker=Speaker.AGENT,
            content="Your order is being checked.",
            turn_number=2,
        )
        first = ConversationMessage(
            session_id=session.session_id,
            speaker=Speaker.CUSTOMER,
            content="Where is my order?",
            turn_number=1,
        )

        self.manager.add_message(second)
        self.manager.add_message(first)

        messages = self.manager.get_messages(session.session_id)

        self.assertEqual([m.turn_number for m in messages], [1, 2])
        self.assertEqual(messages[0].content, "Where is my order?")
        self.assertEqual(
            messages[1].content,
            "Your order is being checked.",
        )


if __name__ == "__main__":
    unittest.main()
