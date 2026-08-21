import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from agent_hub.api import app
from agent_hub.auth import AuthenticatedUser
from agent_hub.database import Database
from agent_hub.dependencies import get_current_user


class AdminUsageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Database(
            Path(self.temporary_directory.name) / "usage.db",
            Fernet.generate_key().decode(),
        )
        self.database.initialize()
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)",
                ("admin", "admin@example.com", "unused", "admin"),
            )
            connection.execute(
                "INSERT INTO agents (id, user_id, name, encrypted_secret) VALUES (?, ?, ?, ?)",
                ("agent", "admin", "Research agent", self.database.encrypt("secret")),
            )
            connection.execute(
                """INSERT INTO agent_usage
                   (agent_id, user_id, conversation_id, event_type, input_chars,
                    output_items, duration_ms)
                   VALUES ('agent', 'admin', 'conversation', 'conversation', 0, 1, 0),
                          ('agent', 'admin', 'conversation', 'message', 18, 2, 1250)"""
            )
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id="admin", email="admin@example.com", role="admin"
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.temporary_directory.cleanup()

    def test_usage_dashboard_aggregates_persisted_agent_events(self) -> None:
        with patch("agent_hub.routes.admin.database", self.database):
            response = self.client.get("/admin/usage?days=30")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_conversations"], 1)
        self.assertEqual(payload["total_interactions"], 2)
        self.assertEqual(payload["active_users"], 1)
        self.assertEqual(payload["input_chars"], 18)
        self.assertEqual(payload["agents"][0]["agent_name"], "Research agent")
        self.assertEqual(payload["agents"][0]["average_duration_ms"], 1250)
        self.assertEqual(len(payload["recent"]), 2)

    def test_usage_dashboard_rejects_unbounded_periods(self) -> None:
        with patch("agent_hub.routes.admin.database", self.database):
            response = self.client.get("/admin/usage?days=1000")

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
