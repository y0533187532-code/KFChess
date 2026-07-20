"""SQLite repository for room metadata and membership history."""

from __future__ import annotations

from .models import RoomRecord


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

    def close(
        self,
        room_id: int,
        *,
        reason: str,
        now_ms: int,
        interrupted: bool = False,
    ) -> bool:
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
