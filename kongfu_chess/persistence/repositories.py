"""Encapsulated SQLite repositories; callers never receive connections."""

from __future__ import annotations

import re
import uuid

from .models import AuthSessionRecord, GameTokenRecord, RoomRecord, UserRecord


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


class AuthSessionRepository:
    def __init__(self, database):
        self._database = database

    def create(
        self, *, user_id: int, token_hash: str, now_ms: int, expires_at_ms: int
    ) -> AuthSessionRecord:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO auth_sessions(
                    user_id, token_hash, created_at_ms, expires_at_ms, last_used_at_ms
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, token_hash, now_ms, expires_at_ms, now_ms),
            )
        return AuthSessionRecord(cursor.lastrowid, user_id, expires_at_ms, now_ms)

    def find_valid(self, token_hash: str, *, now_ms: int) -> AuthSessionRecord | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM auth_sessions
                WHERE token_hash = ? AND revoked_at_ms IS NULL AND expires_at_ms > ?
                """,
                (token_hash, now_ms),
            ).fetchone()
            if row is not None:
                connection.execute(
                    "UPDATE auth_sessions SET last_used_at_ms = ? WHERE id = ?",
                    (now_ms, row["id"]),
                )
        if row is None:
            return None
        return AuthSessionRecord(row["id"], row["user_id"], row["expires_at_ms"], now_ms)

    def revoke(self, token_hash: str, *, now_ms: int) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE auth_sessions SET revoked_at_ms = ?
                WHERE token_hash = ? AND revoked_at_ms IS NULL
                """,
                (now_ms, token_hash),
            )
        return cursor.rowcount == 1


class GameTokenRepository:
    def __init__(self, database):
        self._database = database

    def create(
        self,
        *,
        game_id: str,
        user_id: int,
        token_hash: str,
        role: str,
        color: str | None,
        now_ms: int,
    ) -> GameTokenRecord:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO game_session_tokens(
                    game_id, user_id, token_hash, role, color, issued_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (game_id, user_id, token_hash, role, color, now_ms),
            )
        return GameTokenRecord(cursor.lastrowid, game_id, user_id, role, color, "ACTIVE", None)

    def find_valid(self, token_hash: str, *, game_id: str, now_ms: int) -> GameTokenRecord | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM game_session_tokens
                WHERE token_hash = ? AND game_id = ? AND revoked_at_ms IS NULL
                  AND (status = 'ACTIVE' OR (status = 'GRACE' AND grace_expires_at_ms >= ?))
                """,
                (token_hash, game_id, now_ms),
            ).fetchone()
        return None if row is None else _game_token_record(row)

    def begin_grace(self, token_hash: str, *, grace_expires_at_ms: int) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE game_session_tokens
                SET status = 'GRACE', grace_expires_at_ms = ?
                WHERE token_hash = ? AND status = 'ACTIVE' AND revoked_at_ms IS NULL
                """,
                (grace_expires_at_ms, token_hash),
            )
        return cursor.rowcount == 1

    def revoke(self, token_hash: str, *, now_ms: int) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE game_session_tokens
                SET status = 'REVOKED', revoked_at_ms = ?
                WHERE token_hash = ? AND status != 'REVOKED'
                """,
                (now_ms, token_hash),
            )
        return cursor.rowcount == 1

    def revoke_game(self, game_id: str, *, now_ms: int) -> int:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE game_session_tokens
                SET status = 'REVOKED', revoked_at_ms = ?
                WHERE game_id = ? AND status != 'REVOKED'
                """,
                (now_ms, game_id),
            )
        return cursor.rowcount


class MatchRepository:
    def __init__(self, database):
        self._database = database

    def save_ranked_result(
        self,
        *,
        game_id: str,
        white_user_id: int,
        black_user_id: int,
        outcome: str,
        reason: str,
        white_rating_before: int,
        white_rating_after: int,
        black_rating_before: int,
        black_rating_after: int,
        now_ms: int,
    ) -> bool:
        with self._database.transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM game_results WHERE game_id = ?", (game_id,)
            ).fetchone():
                return False
            connection.execute(
                """
                INSERT INTO game_results(
                    game_id, white_user_id, black_user_id, outcome, reason, ranked,
                    white_rating_before, white_rating_after,
                    black_rating_before, black_rating_after, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    game_id, white_user_id, black_user_id, outcome, reason,
                    white_rating_before, white_rating_after,
                    black_rating_before, black_rating_after, now_ms,
                ),
            )
            connection.execute(
                "UPDATE users SET rating = ?, updated_at_ms = ? WHERE id = ?",
                (white_rating_after, now_ms, white_user_id),
            )
            connection.execute(
                "UPDATE users SET rating = ?, updated_at_ms = ? WHERE id = ?",
                (black_rating_after, now_ms, black_user_id),
            )
            connection.executemany(
                """
                INSERT INTO rating_changes(
                    game_id, user_id, rating_before, rating_after
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    (game_id, white_user_id, white_rating_before, white_rating_after),
                    (game_id, black_user_id, black_rating_before, black_rating_after),
                ),
            )
        return True


class RoomRepository:
    def __init__(self, database):
        self._database = database

    def create(self, *, code: str, creator_user_id: int, now_ms: int) -> RoomRecord:
        normalized = code.upper()
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO rooms(code, creator_user_id, status, created_at_ms)
                VALUES (?, ?, 'WAITING', ?)
                """,
                (normalized, creator_user_id, now_ms),
            )
        return RoomRecord(cursor.lastrowid, normalized, creator_user_id, "WAITING")

    def add_member(
        self,
        *,
        room_id: int,
        user_id: int,
        role: str,
        color: str | None,
        now_ms: int,
    ) -> int:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO room_members(room_id, user_id, role, color, joined_at_ms)
                VALUES (?, ?, ?, ?, ?)
                """,
                (room_id, user_id, role, color, now_ms),
            )
        return cursor.lastrowid

    def leave_member(self, member_id: int, *, now_ms: int) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE room_members SET left_at_ms = ?
                WHERE id = ? AND left_at_ms IS NULL
                """,
                (now_ms, member_id),
            )
        return cursor.rowcount == 1

    def close(self, room_id: int, *, reason: str, now_ms: int, interrupted: bool = False) -> bool:
        status = "INTERRUPTED" if interrupted else "CLOSED"
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE rooms SET status = ?, closed_at_ms = ?, close_reason = ?
                WHERE id = ? AND status IN ('WAITING', 'ACTIVE')
                """,
                (status, now_ms, reason, room_id),
            )
        return cursor.rowcount == 1


def _user_record(row) -> UserRecord:
    return UserRecord(
        row["id"], row["username"], row["password_hash"], row["email"],
        row["phone"], row["rating"], row["status"]
    )


def _game_token_record(row) -> GameTokenRecord:
    return GameTokenRecord(
        row["id"], row["game_id"], row["user_id"], row["role"], row["color"],
        row["status"], row["grace_expires_at_ms"]
    )
