
import json
from datetime import datetime, timezone

from customer_support_coach.data_models import (
    Session,
    ConversationMessage,
    AgentResult,
    InteractionMode,
    SessionStatus,
    Speaker,
)
from customer_support_coach.database import Database


class SessionManager:
    def __init__(self, db_path="data/customer_support.db"):
        self.db = Database(db_path)

    def create_session(self, session):
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, mode, product_context, scenario,
                    customer_persona, status, created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.mode.value,
                    json.dumps(session.product_context),
                    json.dumps(session.scenario),
                    json.dumps(session.customer_persona),
                    session.status.value,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    json.dumps(session.metadata),
                ),
            )
        return session

    def get_session(self, session_id):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()

        if row is None:
            return None

        return Session(
            session_id=row["session_id"],
            mode=InteractionMode(row["mode"]),
            product_context=json.loads(row["product_context"]),
            scenario=json.loads(row["scenario"]) if row["scenario"] else None,
            customer_persona=(
                json.loads(row["customer_persona"])
                if row["customer_persona"] else None
            ),
            status=SessionStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata"]),
        )

    def list_sessions(self):
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT session_id FROM sessions ORDER BY created_at DESC"
            ).fetchall()

        return [self.get_session(row["session_id"]) for row in rows]

    def update_session_status(self, session_id, status):
        if isinstance(status, str):
            status = SessionStatus(status)

        updated_at = datetime.now(timezone.utc).isoformat()

        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE sessions
                SET status = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (status.value, updated_at, session_id),
            )

        return cursor.rowcount > 0

    def add_message(self, message):
        with self.db.connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?",
                (message.session_id,),
            ).fetchone()

            if exists is None:
                raise ValueError(f"Session not found: {message.session_id}")

            conn.execute(
                """
                INSERT INTO messages (
                    message_id, session_id, speaker, content,
                    turn_number, timestamp, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.session_id,
                    message.speaker.value,
                    message.content,
                    message.turn_number,
                    message.timestamp.isoformat(),
                    json.dumps(message.metadata),
                ),
            )

        return message

    def get_messages(self, session_id):
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY turn_number ASC, timestamp ASC, message_id ASC
                """,
                (session_id,),
            ).fetchall()

        return [
            ConversationMessage(
                message_id=row["message_id"],
                session_id=row["session_id"],
                speaker=Speaker(row["speaker"]),
                content=row["content"],
                turn_number=row["turn_number"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]

    def save_agent_result(self, agent_result):
        with self.db.connect() as conn:
            session_exists = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?",
                (agent_result.session_id,),
            ).fetchone()

            if session_exists is None:
                raise ValueError(
                    f"Session not found: {agent_result.session_id}"
                )

            if agent_result.message_id is not None:
                message_exists = conn.execute(
                    "SELECT 1 FROM messages WHERE message_id = ?",
                    (agent_result.message_id,),
                ).fetchone()

                if message_exists is None:
                    raise ValueError(
                        f"Message not found: {agent_result.message_id}"
                    )

            conn.execute(
                """
                INSERT INTO agent_results (
                    result_id, session_id, message_id,
                    agent_type, result, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_result.result_id,
                    agent_result.session_id,
                    agent_result.message_id,
                    agent_result.agent_type,
                    json.dumps(agent_result.result),
                    agent_result.created_at.isoformat(),
                ),
            )

        return agent_result

    def get_agent_results(self, session_id):
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM agent_results
                WHERE session_id = ?
                ORDER BY created_at ASC, result_id ASC
                """,
                (session_id,),
            ).fetchall()

        return [
            AgentResult(
                result_id=row["result_id"],
                session_id=row["session_id"],
                message_id=row["message_id"],
                agent_type=row["agent_type"],
                result=json.loads(row["result"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
