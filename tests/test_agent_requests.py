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


class AgentRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Database(
            Path(self.directory.name) / "requests.db", Fernet.generate_key().decode()
        )
        self.database.initialize()
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)",
                ("admin", "admin@example.com", "unused", "admin"),
            )
            connection.execute(
                "INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)",
                ("member", "member@example.com", "unused", "user"),
            )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.directory.cleanup()

    def authenticate(self, user_id: str, email: str, role: str = "user") -> None:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id=user_id, email=email, role=role
        )

    def test_user_submits_and_sees_only_own_requests(self) -> None:
        self.authenticate("member", "member@example.com")
        with patch("agent_hub.routes.agents.database", self.database):
            response = self.client.post(
                "/agents/requests",
                json={"name": "Contract analyst", "reason": "Review supplier terms"},
            )
            listed = self.client.get("/agents/requests")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "pending")
        self.assertEqual(listed.json()[0]["name"], "Contract analyst")
        self.assertEqual(listed.json()[0]["user_email"], "member@example.com")

    def test_admin_can_review_and_resolve_requests(self) -> None:
        self.authenticate("member", "member@example.com")
        with patch("agent_hub.routes.agents.database", self.database):
            request_id = self.client.post(
                "/agents/requests", json={"name": "Legal", "reason": "Check terms"}
            ).json()["id"]
        self.authenticate("admin", "admin@example.com", "admin")
        with patch("agent_hub.routes.admin.database", self.database):
            listed = self.client.get("/admin/agent-requests")
            updated = self.client.put(
                f"/admin/agent-requests/{request_id}", json={"status": "fulfilled"}
            )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["user_email"], "member@example.com")
        self.assertEqual(updated.json()["status"], "fulfilled")

    def test_regular_user_cannot_open_admin_queue(self) -> None:
        self.authenticate("member", "member@example.com")
        with patch("agent_hub.routes.admin.database", self.database):
            response = self.client.get("/admin/agent-requests")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
