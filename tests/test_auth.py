import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import HTTPException

from agent_hub.auth import AuthService
from agent_hub.database import Database


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Database(
            Path(self.directory.name) / "test.db", Fernet.generate_key().decode()
        )
        self.database.initialize()
        self.auth = AuthService(self.database)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_password_is_hashed_and_session_is_revocable(self) -> None:
        user, token = self.auth.register("User@Example.com", "correct horse battery")

        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user.id,)
            ).fetchone()
            session = connection.execute("SELECT token_hash FROM sessions").fetchone()

        self.assertNotIn("correct horse battery", row["password_hash"])
        self.assertNotEqual(session["token_hash"], token)
        self.assertEqual(self.auth.authenticate(token).id, user.id)
        self.auth.logout(token)
        with self.assertRaises(HTTPException):
            self.auth.authenticate(token)

    def test_wrong_password_is_rejected(self) -> None:
        self.auth.register("user@example.com", "correct horse battery")

        with self.assertRaises(HTTPException) as raised:
            self.auth.login("user@example.com", "incorrect password")

        self.assertEqual(raised.exception.status_code, 401)

    def test_first_registered_user_is_admin_and_later_users_are_not(self) -> None:
        first, _ = self.auth.register("admin@example.com", "correct horse battery")
        second, _ = self.auth.register("member@example.com", "correct horse battery")

        self.assertEqual(first.role, "admin")
        self.assertEqual(second.role, "user")
        self.assertEqual(self.auth.login(first.email, "correct horse battery")[0].role, "admin")

    def test_agent_secrets_use_authenticated_encryption(self) -> None:
        encrypted = self.database.encrypt("shared-agent-secret")

        self.assertNotIn(b"shared-agent-secret", encrypted)
        self.assertEqual(self.database.decrypt(encrypted), "shared-agent-secret")


if __name__ == "__main__":
    unittest.main()
