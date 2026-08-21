import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from cryptography.fernet import Fernet, InvalidToken


PASSWORD_N = 2**14
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30


class Database:
    def __init__(self, path: Path, encryption_key: str) -> None:
        self.path = path
        try:
            self.cipher = Fernet(encryption_key.encode())
        except (TypeError, ValueError) as error:
            raise RuntimeError("AGENT_HUB_ENCRYPTION_KEY must be a Fernet key") from error

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at INTEGER NOT NULL DEFAULT (unixepoch())
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL DEFAULT (unixepoch())
                );
                CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id);
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    encrypted_secret BLOB NOT NULL,
                    created_at INTEGER NOT NULL DEFAULT (unixepoch())
                );
                CREATE INDEX IF NOT EXISTS agents_user_id ON agents(user_id);
                CREATE TABLE IF NOT EXISTS agent_requests (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
                    updated_at INTEGER NOT NULL DEFAULT (unixepoch())
                );
                CREATE INDEX IF NOT EXISTS agent_requests_user_id
                    ON agent_requests(user_id, created_at);
                CREATE INDEX IF NOT EXISTS agent_requests_status
                    ON agent_requests(status, created_at);
                CREATE TABLE IF NOT EXISTS agent_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    conversation_id TEXT,
                    event_type TEXT NOT NULL,
                    input_chars INTEGER NOT NULL DEFAULT 0,
                    output_items INTEGER NOT NULL DEFAULT 0,
                    attachment_count INTEGER NOT NULL DEFAULT 0,
                    attachment_bytes INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL DEFAULT (unixepoch())
                );
                CREATE INDEX IF NOT EXISTS agent_usage_created_at
                    ON agent_usage(created_at);
                CREATE INDEX IF NOT EXISTS agent_usage_agent_created
                    ON agent_usage(agent_id, created_at);
                CREATE INDEX IF NOT EXISTS agent_usage_user_created
                    ON agent_usage(user_id, created_at);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(users)").fetchall()
            }
            if "role" not in columns:
                connection.execute(
                    "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_agents (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
                    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
                    PRIMARY KEY (user_id, agent_id)
                );
                CREATE INDEX IF NOT EXISTS user_agents_agent_id
                    ON user_agents(agent_id);
                INSERT OR IGNORE INTO user_agents (user_id, agent_id)
                    SELECT user_id, id FROM agents;
                """
            )
            if connection.execute(
                "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
            ).fetchone() is None:
                first_user = connection.execute(
                    "SELECT id FROM users ORDER BY created_at, id LIMIT 1"
                ).fetchone()
                if first_user is not None:
                    connection.execute(
                        "UPDATE users SET role = 'admin' WHERE id = ?",
                        (first_user["id"],),
                    )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def encrypt(self, value: str) -> bytes:
        return self.cipher.encrypt(value.encode())

    def decrypt(self, value: bytes) -> str:
        try:
            return self.cipher.decrypt(value).decode()
        except InvalidToken as error:
            raise RuntimeError("Unable to decrypt an agent secret") from error


def load_database() -> Database:
    path = Path(os.getenv("AGENT_HUB_DATABASE", "data/agent-hub.db"))
    configured_key = os.getenv("AGENT_HUB_ENCRYPTION_KEY", "").strip()
    if configured_key:
        key = configured_key
    else:
        key_path = path.with_suffix(path.suffix + ".key")
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if key_path.exists():
            key = key_path.read_text().strip()
        else:
            key = Fernet.generate_key().decode()
            key_path.write_text(key)
            os.chmod(key_path, 0o600)
    database = Database(path, key)
    database.initialize()
    return database


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=PASSWORD_N, r=8, p=1, dklen=32
    )
    return f"scrypt${PASSWORD_N}$8$1${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=_decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_decode(expected)),
        )
        return hmac.compare_digest(digest, _decode(expected))
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
