"""SQLite repository for game-seat and spectator token hashes."""

from __future__ import annotations

from .models import GameTokenRecord


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

    def find_valid(
        self, token_hash: str, *, game_id: str, now_ms: int
    ) -> GameTokenRecord | None:
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


def _game_token_record(row) -> GameTokenRecord:
    return GameTokenRecord(
        row["id"],
        row["game_id"],
        row["user_id"],
        row["role"],
        row["color"],
        row["status"],
        row["grace_expires_at_ms"],
    )
