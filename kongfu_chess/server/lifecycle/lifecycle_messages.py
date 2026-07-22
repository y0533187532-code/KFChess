"""Build lifecycle protocol responses shared by handlers and push services."""

from __future__ import annotations

from ...protocol import MessageType
from ..app.routing import OutgoingMessage
from ..core.chess_compatibility import CHESS_SEAT_ADAPTER
from .game_lifecycle_models import GameLifecycleState, GameLifecycleView


def lifecycle_outgoing(
    view: GameLifecycleView,
    *,
    now_ms: int,
    seat_adapter=CHESS_SEAT_ADAPTER,
    paused_message: bool = False,
) -> OutgoingMessage:
    message_type = MessageType.GAME_LIFECYCLE_STATUS
    if view.state is GameLifecycleState.CANCELLED:
        message_type = MessageType.GAME_CANCELLED
    elif view.state is GameLifecycleState.ENDED:
        message_type = (
            MessageType.GAME_FORFEIT
            if view.terminal_reason == "forfeit"
            else MessageType.GAME_OVER
        )
    elif view.state is GameLifecycleState.PAUSED_FOR_RECONNECT and paused_message:
        message_type = MessageType.DISCONNECT_COUNTDOWN

    payload = {
        "accepted": True,
        "code": "ok",
        "game_id": view.game_id,
        "mode": view.mode.value,
        "ranked": view.ranked,
        "state": view.state.value,
        "version": view.version,
        "players": [
            {
                "user_id": player.user_id,
                "seat": player.seat.value,
                "color": seat_adapter.protocol_color(player.seat),
                "connected": player.connected,
            }
            for player in view.players
        ],
    }
    if view.reconnect_deadline_ms is not None:
        payload["reconnect_deadline_ms"] = view.reconnect_deadline_ms
        payload["remaining_ms"] = max(0, view.reconnect_deadline_ms - now_ms)
    if view.winner_seat is not None:
        payload["winner_seat"] = view.winner_seat.value
        payload["winner_color"] = seat_adapter.protocol_color(view.winner_seat)
    if view.terminal_reason is not None:
        payload["reason"] = view.terminal_reason
    return OutgoingMessage(message_type.value, payload)
