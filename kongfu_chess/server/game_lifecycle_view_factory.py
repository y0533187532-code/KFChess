"""Construct immutable lifecycle views from persistence records."""

from __future__ import annotations

from .game_lifecycle_models import (
    GameLifecycleState,
    GameLifecycleView,
    LifecyclePlayer,
)
from .game_mode import GameMode, PlayerSeat


class GameLifecycleViewFactory:
    def __init__(self, lifecycle_repository):
        self._lifecycles = lifecycle_repository

    def create(self, record, *, changed: bool = True) -> GameLifecycleView:
        players = tuple(
            LifecyclePlayer(
                item.user_id,
                PlayerSeat(item.seat),
                item.connected,
                item.reconnect_deadline_ms,
                item.meaningful_activity,
            )
            for item in self._lifecycles.players(record.game_id)
        )
        deadlines = tuple(
            player.reconnect_deadline_ms
            for player in players
            if not player.connected and player.reconnect_deadline_ms is not None
        )
        return GameLifecycleView(
            game_id=record.game_id,
            mode=GameMode(record.mode),
            ranked=record.ranked,
            state=GameLifecycleState(record.state),
            players=players,
            version=record.version,
            reconnect_deadline_ms=min(deadlines) if deadlines else None,
            winner_seat=(
                None if record.winner_seat is None else PlayerSeat(record.winner_seat)
            ),
            terminal_reason=record.terminal_reason,
            changed=changed,
        )
