"""Pure reconnect deadlines and paused-game outcome decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .game_lifecycle_models import GameLifecycleState
from .game_mode import GameMode


class ReconnectAction(str, Enum):
    NONE = "NONE"
    RESUME = "RESUME"
    FORFEIT = "FORFEIT"
    CANCEL = "CANCEL"


@dataclass(frozen=True)
class ReconnectDecision:
    action: ReconnectAction
    reason: str | None = None
    forfeiting_player: object | None = None


class ReconnectPolicy:
    def __init__(self, *, grace_seconds: int):
        self._grace_ms = grace_seconds * 1000

    def deadline(self, now_ms: int) -> int:
        return now_ms + self._grace_ms

    @staticmethod
    def is_double_disconnect(players) -> bool:
        return sum(not player.connected for player in players) == 2

    @staticmethod
    def should_resume(players) -> bool:
        return all(player.connected for player in players)

    @staticmethod
    def reconnect_has_expired(player, *, now_ms: int) -> bool:
        return (
            player.reconnect_deadline_ms is None
            or now_ms >= player.reconnect_deadline_ms
        )

    def expiry_decision(self, record, players, *, now_ms: int) -> ReconnectDecision:
        if record.state != GameLifecycleState.PAUSED_FOR_RECONNECT.value:
            return ReconnectDecision(ReconnectAction.NONE)
        expired = tuple(
            player
            for player in players
            if not player.connected
            and player.reconnect_deadline_ms is not None
            and now_ms >= player.reconnect_deadline_ms
        )
        if not expired:
            return ReconnectDecision(ReconnectAction.NONE)
        if record.double_disconnect:
            return ReconnectDecision(ReconnectAction.CANCEL, "double_disconnect")
        forfeiting = expired[0]
        if record.mode == GameMode.PLAY.value and not forfeiting.meaningful_activity:
            return ReconnectDecision(
                ReconnectAction.CANCEL, "no_meaningful_activity"
            )
        return ReconnectDecision(
            ReconnectAction.FORFEIT,
            "forfeit",
            forfeiting_player=forfeiting,
        )
