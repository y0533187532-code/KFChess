"""SQLite room metadata and append-only membership history."""

from __future__ import annotations

from .models import RoomMemberRecord, RoomRecord


class RoomRepository:
    def __init__(self, database):
        self._database = database

    def create(
        self,
        *,
        code: str,
        game_id: str,
        creator_user_id: int,
        now_ms: int,
    ) -> RoomRecord:
        normalized = code.upper()
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO rooms(
                    code, game_id, creator_user_id, status, created_at_ms
                ) VALUES (?, ?, ?, 'WAITING', ?)
                """,
                (normalized, game_id, creator_user_id, now_ms),
            )
            row = connection.execute(
                "SELECT * FROM rooms WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return _room_record(row)

    def by_code(self, code: str) -> RoomRecord | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM rooms WHERE code = ?", (code.upper(),)
            ).fetchone()
        return None if row is None else _room_record(row)

    def by_id(self, room_id: int) -> RoomRecord | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM rooms WHERE id = ?", (room_id,)
            ).fetchone()
        return None if row is None else _room_record(row)

    def count_open(self) -> int:
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM rooms WHERE status IN ('WAITING', 'ACTIVE')"
            ).fetchone()
        return row[0]

    def open_rooms(self) -> tuple[RoomRecord, ...]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM rooms
                WHERE status IN ('WAITING', 'ACTIVE')
                ORDER BY id
                """
            ).fetchall()
        return tuple(_room_record(row) for row in rows)

    def add_member(
        self,
        *,
        room_id: int,
        user_id: int,
        role: str,
        color: str | None,
        now_ms: int,
    ) -> RoomMemberRecord:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO room_members(
                    room_id, user_id, role, color, joined_at_ms
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (room_id, user_id, role, color, now_ms),
            )
            row = connection.execute(
                "SELECT * FROM room_members WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return _member_record(row)

    def active_members(self, room_id: int) -> tuple[RoomMemberRecord, ...]:
        with self._database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT * FROM room_members
                WHERE room_id = ? AND left_at_ms IS NULL
                ORDER BY joined_at_ms, id
                """,
                (room_id,),
            ).fetchall()
        return tuple(_member_record(row) for row in rows)

    def active_membership_for_user(
        self, user_id: int
    ) -> RoomMemberRecord | None:
        with self._database.transaction() as connection:
            row = connection.execute(
                """
                SELECT rm.* FROM room_members rm
                JOIN rooms r ON r.id = rm.room_id
                WHERE rm.user_id = ? AND rm.left_at_ms IS NULL
                  AND r.status IN ('WAITING', 'ACTIVE')
                ORDER BY rm.id LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return None if row is None else _member_record(row)

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

    def activate(self, room_id: int) -> bool:
        return self._transition(room_id, "WAITING", "ACTIVE")

    def return_to_waiting(self, room_id: int) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE rooms SET status = 'WAITING'
                WHERE id = ? AND status = 'ACTIVE' AND started_at_ms IS NULL
                """,
                (room_id,),
            )
        return cursor.rowcount == 1

    def mark_started(self, room_id: int, *, now_ms: int) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE rooms SET started_at_ms = ?
                WHERE id = ? AND status = 'ACTIVE' AND started_at_ms IS NULL
                """,
                (now_ms, room_id),
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

    def end(self, room_id: int, *, reason: str, now_ms: int) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE rooms SET status = 'ENDED', closed_at_ms = ?, close_reason = ?
                WHERE id = ? AND status = 'ACTIVE'
                """,
                (now_ms, reason, room_id),
            )
        return cursor.rowcount == 1

    def recover_open_rooms(self, *, now_ms: int) -> tuple[int, int]:
        with self._database.transaction() as connection:
            interrupted = connection.execute(
                """
                UPDATE rooms SET status = 'INTERRUPTED', closed_at_ms = ?,
                    close_reason = 'server_restart'
                WHERE status = 'ACTIVE'
                """,
                (now_ms,),
            ).rowcount
            closed = connection.execute(
                """
                UPDATE rooms SET status = 'CLOSED', closed_at_ms = ?,
                    close_reason = 'server_restart'
                WHERE status = 'WAITING'
                """,
                (now_ms,),
            ).rowcount
        return interrupted, closed

    def _transition(self, room_id: int, current: str, target: str) -> bool:
        with self._database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE rooms SET status = ? WHERE id = ? AND status = ?",
                (target, room_id, current),
            )
        return cursor.rowcount == 1


def _room_record(row) -> RoomRecord:
    return RoomRecord(
        row["id"],
        row["code"],
        row["game_id"],
        row["creator_user_id"],
        row["status"],
        row["started_at_ms"],
    )


def _member_record(row) -> RoomMemberRecord:
    return RoomMemberRecord(
        row["id"],
        row["room_id"],
        row["user_id"],
        row["role"],
        row["color"],
        row["joined_at_ms"],
        row["left_at_ms"],
    )
