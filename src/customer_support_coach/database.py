"""SQLite persistence layer for the Customer Support Coaching Assistant."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    """Manage SQLite connections and database schema."""

    def __init__(self, db_path="data/customer_support.db"):
        self.db_path = str(db_path)

        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(
                parents=True, exist_ok=True
            )

        self.initialize()

    @contextmanager
    def connect(self):
        """Open a connection and always close it after use."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    product_context TEXT NOT NULL,
                    scenario TEXT,
                    customer_persona TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    content TEXT NOT NULL,
                    turn_number INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    FOREIGN KEY (session_id)
                        REFERENCES sessions(session_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS agent_results (
                    result_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    message_id TEXT,
                    agent_type TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id)
                        REFERENCES sessions(session_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (message_id)
                        REFERENCES messages(message_id)
                        ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session_turn
                ON messages(session_id, turn_number, timestamp);

                CREATE INDEX IF NOT EXISTS idx_results_session
                ON agent_results(session_id, created_at);
            """)

    @staticmethod
    def encode_json(value):
        return json.dumps(value, allow_nan=False)

    @staticmethod
    def decode_json(value):
        return json.loads(value)
