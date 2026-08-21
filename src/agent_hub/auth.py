import secrets
import sqlite3
import time
from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException, status

from agent_hub.database import (
    SESSION_TTL_SECONDS,
    Database,
    hash_password,
    token_hash,
    verify_password,
)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str
    role: str = "user"


class AuthService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def register(self, email: str, password: str) -> tuple[AuthenticatedUser, str]:
        try:
            with self.database.connect() as connection:
                role = (
                    "admin"
                    if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone()
                    is None
                    else "user"
                )
                user = AuthenticatedUser(
                    id=uuid4().hex, email=email.strip().lower(), role=role
                )
                connection.execute(
                    """INSERT INTO users (id, email, password_hash, role)
                       VALUES (?, ?, ?, ?)""",
                    (user.id, user.email, hash_password(password), user.role),
                )
        except sqlite3.IntegrityError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from error
        return user, self._create_session(user.id)

    def login(self, email: str, password: str) -> tuple[AuthenticatedUser, str]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT id, email, password_hash, role FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
        user = AuthenticatedUser(
            id=row["id"], email=row["email"], role=row["role"]
        )
        return user, self._create_session(user.id)

    def authenticate(self, token: str) -> AuthenticatedUser:
        now = int(time.time())
        with self.database.connect() as connection:
            row = connection.execute(
                """SELECT users.id, users.email, users.role FROM sessions
                   JOIN users ON users.id = sessions.user_id
                   WHERE sessions.token_hash = ? AND sessions.expires_at > ?""",
                (token_hash(token), now),
            ).fetchone()
        if row is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return AuthenticatedUser(
            id=row["id"], email=row["email"], role=row["role"]
        )

    def logout(self, token: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),)
            )

    def _create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.database.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (token_hash(token), user_id, now + SESSION_TTL_SECONDS),
            )
        return token
