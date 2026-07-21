"""SQLite persistence for authoritative game lifecycle and reconnect state."""

from __future__ import annotations

from .models import GameLifecyclePlayerRecord, GameLifecycleRecord


class GameLifecycleRepository:
    _TERMINAL_STATES = frozenset({"ENDED", "CANCELLED", "INTERRUPTED"})

    def __init__(self, database):
        self._database = database

    def create(
        self,
        *,
        game_id: str,
        mode: str,
        ranked: bool,
        state: str,
        players,
        now_ms: int,
        room_id: int | None = None,
    ) -> GameLifecycleRecord:
        started_at_ms = now_ms if state == "ACTIVE" else None
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO game_lifecycles(
                    game_id, mode, ranked, state, room_id,
                    created_at_ms, started_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    game_id,
                    mode,
                    int(ranked),
                    state,
                    room_id,
                    now_ms,
                    started_at_ms,
                ),
            )
            connection.executemany(
                """
                INSERT INTO game_lifecycle_players(game_id, user_id, seat)
                VALUES (?, ?, ?)
                """,
                ((game_id, user_id, seat) for user_id, seat in players),
            )
            row = connection.execute(
                "SELECT * FROM game_lifecycles WHERE game_id = ?", (game_id,)
            ).fetchone()
        return _lifecycle_record(row)

    def add_player(self, game_id: str, user_id: int, seat: str) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO game_lifecycle_players(game_id, user_id, seat)
                SELECT game_id, ?, ? FROM game_lifecycles
                WHERE game_id = ? AND state IN ('CREATED', 'WAITING_TO_START')
                """,
                (user_id, seat, game_id),
            )
        return cursor.rowcount == 1

    def remove_player(self, game_id: str, user_id: int) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                DELETE FROM game_lifecycle_players
                WHERE game_id = ? AND user_id = ?
                  AND EXISTS (
                      SELECT 1 FROM game_lifecycles lifecycle
                      WHERE lifecycle.game_id = game_lifecycle_players.game_id
                        AND lifecycle.state IN ('CREATED', 'WAITING_TO_START')
                  )
                """,
                (game_id, user_id),
            )
        return cursor.rowcount == 1

    def by_id(self, game_id: str) -> GameLifecycleRecord | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM game_lifecycles WHERE game_id = ?", (game_id,)
            ).fetchone()
        return None if row is None else _lifecycle_record(row)

    def user_in_live_game(self, user_id: int) -> bool:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM game_lifecycle_players player
                JOIN game_lifecycles lifecycle
                  ON lifecycle.game_id = player.game_id
                WHERE player.user_id = ?
                  AND lifecycle.state NOT IN ('ENDED', 'CANCELLED', 'INTERRUPTED')
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return row is not None

    def players(self, game_id: str) -> tuple[GameLifecyclePlayerRecord, ...]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM game_lifecycle_players
                WHERE game_id = ?
                ORDER BY CASE seat
                    WHEN 'FIRST_PLAYER' THEN 0 ELSE 1 END
                """,
                (game_id,),
            ).fetchall()
        return tuple(_player_record(row) for row in rows)

    def paused(self) -> tuple[GameLifecycleRecord, ...]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM game_lifecycles
                WHERE state = 'PAUSED_FOR_RECONNECT'
                ORDER BY created_at_ms, game_id
                """
            ).fetchall()
        return tuple(_lifecycle_record(row) for row in rows)

    def transition(
        self,
        game_id: str,
        *,
        from_states,
        target: str,
        now_ms: int,
        reason: str | None = None,
        winner_seat: str | None = None,
        double_disconnect: bool | None = None,
    ) -> bool:
        states = tuple(from_states)
        placeholders = ", ".join("?" for _ in states)
        terminal = target in self._TERMINAL_STATES
        with self._database.transaction() as connection:
            cursor = connection.execute(
                f"""
                UPDATE game_lifecycles
                SET state = ?, version = version + 1,
                    started_at_ms = CASE
                        WHEN ? = 'ACTIVE' THEN COALESCE(started_at_ms, ?)
                        ELSE started_at_ms END,
                    ended_at_ms = CASE WHEN ? THEN ? ELSE ended_at_ms END,
                    terminal_reason = CASE WHEN ? THEN ? ELSE terminal_reason END,
                    winner_seat = CASE WHEN ? THEN ? ELSE winner_seat END,
                    double_disconnect = COALESCE(?, double_disconnect)
                WHERE game_id = ? AND state IN ({placeholders})
                """,
                (
                    target,
                    target,
                    now_ms,
                    int(terminal),
                    now_ms,
                    int(terminal),
                    reason,
                    int(terminal),
                    winner_seat,
                    None if double_disconnect is None else int(double_disconnect),
                    game_id,
                    *states,
                ),
            )
        return cursor.rowcount == 1

    def disconnect_player(
        self, game_id: str, user_id: int, *, deadline_ms: int
    ) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE game_lifecycle_players
                SET connected = 0, reconnect_deadline_ms = ?
                WHERE game_id = ? AND user_id = ? AND connected = 1
                """,
                (deadline_ms, game_id, user_id),
            )
        return cursor.rowcount == 1

    def reconnect_player(self, game_id: str, user_id: int) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE game_lifecycle_players
                SET connected = 1, reconnect_deadline_ms = NULL
                WHERE game_id = ? AND user_id = ? AND connected = 0
                """,
                (game_id, user_id),
            )
        return cursor.rowcount == 1

    def mark_meaningful_activity(self, game_id: str, user_id: int) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE game_lifecycle_players SET meaningful_activity = 1
                WHERE game_id = ? AND user_id = ? AND meaningful_activity = 0
                  AND EXISTS (
                      SELECT 1 FROM game_lifecycles lifecycle
                      WHERE lifecycle.game_id = game_lifecycle_players.game_id
                        AND lifecycle.state = 'ACTIVE'
                  )
                """,
                (game_id, user_id),
            )
        return cursor.rowcount == 1

    def recover_nonterminal(self, *, now_ms: int):
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM game_lifecycles
                WHERE state NOT IN ('ENDED', 'CANCELLED', 'INTERRUPTED')
                ORDER BY created_at_ms, game_id
                """
            ).fetchall()
            connection.execute(
                """
                UPDATE game_lifecycles
                SET state = CASE
                        WHEN state IN ('ACTIVE', 'PAUSED_FOR_RECONNECT')
                            THEN 'INTERRUPTED'
                        ELSE 'CANCELLED'
                    END,
                    terminal_reason = 'server_restart', ended_at_ms = ?,
                    version = version + 1
                WHERE state NOT IN ('ENDED', 'CANCELLED', 'INTERRUPTED')
                """,
                (now_ms,),
            )
        return tuple(_lifecycle_record(row) for row in rows)


def _lifecycle_record(row) -> GameLifecycleRecord:
    return GameLifecycleRecord(
        row["game_id"],
        row["mode"],
        bool(row["ranked"]),
        row["state"],
        row["room_id"],
        bool(row["double_disconnect"]),
        row["winner_seat"],
        row["terminal_reason"],
        row["version"],
        row["created_at_ms"],
        row["started_at_ms"],
        row["ended_at_ms"],
    )


def _player_record(row) -> GameLifecyclePlayerRecord:
    return GameLifecyclePlayerRecord(
        row["game_id"],
        row["user_id"],
        row["seat"],
        bool(row["connected"]),
        row["reconnect_deadline_ms"],
        bool(row["meaningful_activity"]),
    )
