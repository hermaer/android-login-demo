"""Local SQLite accounts for the first OFFLINE prototype.

This is deliberately not a server-backed identity system. Each installation has
its own private database. Passwords are never stored in plaintext.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

ITERATIONS = 350_000
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class User:
    id: int
    name: str
    email: str


def default_database_path() -> Path:
    # Flet sets this environment variable on Android and in the desktop client.
    # The directory is private to the app and survives application updates.
    data_dir = Path(os.environ.get("FLET_APP_STORAGE_DATA") or (Path.cwd() / ".local_data"))
    return data_dir / "users.sqlite3"


class UserRepository:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else default_database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.db_path), timeout=10)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _create_schema(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @staticmethod
    def _email(value: str) -> str:
        email = value.strip().lower()
        if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
            raise ValueError("Введите корректный адрес электронной почты.")
        return email

    def register(self, name: str, email: str, password: str) -> User:
        name = " ".join(name.split())
        email = self._email(email)
        if not (2 <= len(name) <= 80):
            raise ValueError("Имя должно содержать от 2 до 80 символов.")
        if not (8 <= len(password) <= 128):
            raise ValueError("Пароль должен содержать от 8 до 128 символов.")

        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
        try:
            with self._connect() as db:
                cursor = db.execute(
                    "INSERT INTO users (name, email, password_salt, password_hash) VALUES (?, ?, ?, ?)",
                    (name, email, salt, digest),
                )
                user_id = cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError("Пользователь с таким email уже зарегистрирован.") from exc
        return User(id=int(user_id), name=name, email=email)

    def authenticate(self, email: str, password: str) -> User | None:
        # The same generic error is used for unknown emails and wrong passwords.
        email = email.strip().lower()
        if not email or not password:
            return None
        with self._connect() as db:
            row = db.execute(
                "SELECT id, name, email, password_salt, password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        if row is None:
            return None
        user_id, name, saved_email, salt, saved_hash = row
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
        if not hmac.compare_digest(candidate, saved_hash):
            return None
        return User(id=user_id, name=name, email=saved_email)
