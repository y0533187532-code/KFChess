"""SQLite repository for user accounts and profile anonymization."""

from __future__ import annotations

import re
import uuid

from .models import UserRecord


_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")


class UserRepository:
    def __init__(self, database, *, username_min_length: int, username_max_length: int):
        self._database = database
        self._username_min_length = username_min_length
        self._username_max_length = username_max_length

    def create(
        self,
        *,
        username: str,
        password_hash: str,
        email: str,
        phone: str,
        initial_rating: int,
        now_ms: int,
    ) -> UserRecord:
        self._validate_username(username)
        if not password_hash:
            raise ValueError("password_hash must not be empty")
        normalized_email = email.strip().casefold()
        normalized_phone = re.sub(r"[\s()-]", "", phone)
        if _EMAIL_PATTERN.fullmatch(normalized_email) is None:
            raise ValueError("email is invalid")
        if _PHONE_PATTERN.fullmatch(normalized_phone) is None:
            raise ValueError("phone is invalid")
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users(
                    username, password_hash, email, phone, rating,
                    created_at_ms, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    password_hash,
                    normalized_email,
                    normalized_phone,
                    initial_rating,
                    now_ms,
                    now_ms,
                ),
            )
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return _user_record(row)

    def by_username(self, username: str) -> UserRecord | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ? COLLATE BINARY", (username,)
            ).fetchone()
        return None if row is None else _user_record(row)

    def by_id(self, user_id: int) -> UserRecord | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return None if row is None else _user_record(row)

    def anonymize(self, user_id: int, *, now_ms: int) -> bool:
        anonymous_name = f"deleted_{uuid.uuid4().hex}"
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET username = ?, password_hash = '', email = NULL, phone = NULL,
                    status = 'ANONYMIZED', updated_at_ms = ?
                WHERE id = ? AND status != 'ANONYMIZED'
                """,
                (anonymous_name, now_ms, user_id),
            )
            connection.execute(
                "UPDATE auth_sessions SET revoked_at_ms = ? WHERE user_id = ? AND revoked_at_ms IS NULL",
                (now_ms, user_id),
            )
            connection.execute(
                """
                UPDATE game_session_tokens
                SET status = 'REVOKED', revoked_at_ms = ?
                WHERE user_id = ? AND status != 'REVOKED'
                """,
                (now_ms, user_id),
            )
        return cursor.rowcount == 1

    def _validate_username(self, username: str) -> None:
        if not self._username_min_length <= len(username) <= self._username_max_length:
            raise ValueError("username length is invalid")
        if _USERNAME_PATTERN.fullmatch(username) is None:
            raise ValueError("username contains invalid characters")


def _user_record(row) -> UserRecord:
    return UserRecord(
        row["id"],
        row["username"],
        row["password_hash"],
        row["email"],
        row["phone"],
        row["rating"],
        row["status"],
    )
