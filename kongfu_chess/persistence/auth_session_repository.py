"""SQLite repository for authentication-session token hashes."""

from __future__ import annotations

from .models import AuthSessionRecord, AuthSessionValidation


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
        validation = self.validate(token_hash, now_ms=now_ms)
        return validation.session

    def validate(self, token_hash: str, *, now_ms: int) -> AuthSessionValidation:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM auth_sessions WHERE token_hash = ?", (token_hash,)
            ).fetchone()
            if (
                row is not None
                and row["revoked_at_ms"] is None
                and row["expires_at_ms"] > now_ms
            ):
                connection.execute(
                    "UPDATE auth_sessions SET last_used_at_ms = ? WHERE id = ?",
                    (now_ms, row["id"]),
                )
        if row is None:
            return AuthSessionValidation("MISSING", None)
        if row["revoked_at_ms"] is not None:
            return AuthSessionValidation("REVOKED", None)
        if row["expires_at_ms"] <= now_ms:
            return AuthSessionValidation("EXPIRED", None)
        session = AuthSessionRecord(
            row["id"], row["user_id"], row["expires_at_ms"], now_ms
        )
        return AuthSessionValidation("VALID", session)

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

    def revoke_user(self, user_id: int, *, now_ms: int) -> int:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE auth_sessions SET revoked_at_ms = ?
                WHERE user_id = ? AND revoked_at_ms IS NULL
                """,
                (now_ms, user_id),
            )
        return cursor.rowcount
