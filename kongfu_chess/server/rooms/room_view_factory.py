"""Build caller-scoped room views from persisted room membership."""

from __future__ import annotations

from typing import Callable, Mapping

from ..core.game_mode import GameRole, SeatBoundaryAdapter
from .room_models import RoomStatus, RoomView


class RoomViewFactory:
    def __init__(
        self,
        room_repository,
        seat_adapter: SeatBoundaryAdapter,
        *,
        snapshot_provider: Callable[[str], Mapping | None] | None = None,
    ):
        self._rooms = room_repository
        self._seat_adapter = seat_adapter
        self._snapshot_provider = snapshot_provider or (lambda _game_id: None)

    def create(
        self,
        room,
        member,
        *,
        game_token: str | None = None,
        leave_deferred: bool = False,
        departed: bool = False,
    ) -> RoomView:
        members = self._rooms.active_members(room.id)
        role = GameRole(member.role)
        seat = None
        if role is GameRole.PLAYER and member.color is not None:
            seat = self._seat_adapter.seat_for_color(member.color)
        return RoomView(
            room_id=room.id,
            code=room.code,
            game_id=room.game_id,
            status=RoomStatus(room.status),
            role=role,
            seat=seat,
            game_token=game_token,
            player_count=sum(item.role == GameRole.PLAYER.value for item in members),
            spectator_count=sum(
                item.role == GameRole.SPECTATOR.value for item in members
            ),
            gameplay_started=room.started_at_ms is not None,
            snapshot=(
                self._snapshot_provider(room.game_id)
                if role is GameRole.SPECTATOR and not departed
                else None
            ),
            leave_deferred=leave_deferred,
        )
