"""SQLite repository for idempotent ranked results and rating changes."""

from __future__ import annotations


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
                    game_id,
                    white_user_id,
                    black_user_id,
                    outcome,
                    reason,
                    white_rating_before,
                    white_rating_after,
                    black_rating_before,
                    black_rating_after,
                    now_ms,
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
