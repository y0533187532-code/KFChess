"""Protocol handlers for authenticated room management."""

from __future__ import annotations

from ..protocol import MessageType, ProtocolError, ProtocolErrorCode
from .auth_service import AuthError
from .chess_compatibility import CHESS_SEAT_ADAPTER
from .game_mode import GameRole, SeatBoundaryAdapter
from .room_models import RoomsError, RoomView
from .routing import OutgoingMessage


class RoomsHandlers:
    def __init__(
        self,
        rooms_service,
        *,
        clock_ms,
        seat_adapter: SeatBoundaryAdapter = CHESS_SEAT_ADAPTER,
    ):
        self._rooms_service = rooms_service
        self._clock_ms = clock_ms
        self._seat_adapter = seat_adapter

    def register_routes(self, router) -> None:
        router.register(MessageType.ROOM_CREATE.value, self.create)
        router.register(MessageType.ROOM_JOIN.value, self.join)
        router.register(MessageType.ROOM_LEAVE.value, self.leave)
        router.register(MessageType.ROOM_STATUS.value, self.status)

    def create(self, context) -> OutgoingMessage:
        auth_token = self._payload(context, requires_code=False)["auth_token"]
        return self._execute(
            lambda: self._room_message(
                self._rooms_service.create(auth_token, now_ms=self._clock_ms())
            )
        )

    def join(self, context) -> OutgoingMessage:
        payload = self._payload(context, requires_code=True)
        return self._execute(
            lambda: self._room_message(
                self._rooms_service.join(
                    payload["auth_token"], payload["code"], now_ms=self._clock_ms()
                )
            )
        )

    def leave(self, context) -> OutgoingMessage:
        payload = self._payload(context, requires_code=True)
        return self._execute(
            lambda: self._room_message(
                self._rooms_service.leave(
                    payload["auth_token"], payload["code"], now_ms=self._clock_ms()
                )
            )
        )

    def status(self, context) -> OutgoingMessage:
        payload = self._payload(context, requires_code=True)
        return self._execute(
            lambda: self._room_message(
                self._rooms_service.status(
                    payload["auth_token"], payload["code"], now_ms=self._clock_ms()
                )
            )
        )

    @staticmethod
    def _payload(context, *, requires_code: bool):
        payload = context.envelope.payload
        expected = {"auth_token", "code"} if requires_code else {"auth_token"}
        if set(payload) != expected or not all(
            isinstance(payload.get(field), str) and payload[field]
            for field in expected
        ):
            raise ProtocolError(
                ProtocolErrorCode.INVALID_FIELD,
                "Room payload does not match its schema",
            )
        return payload

    @classmethod
    def _execute(cls, action) -> OutgoingMessage:
        try:
            return action()
        except (AuthError, RoomsError) as exc:
            return OutgoingMessage(
                MessageType.COMMAND_RESULT.value,
                {"accepted": False, "code": exc.code.value},
            )

    def _room_message(self, view: RoomView) -> OutgoingMessage:
        payload = {
            "accepted": True,
            "code": "ok",
            "room_id": view.room_id,
            "code": view.code,
            "game_id": view.game_id,
            "status": view.status.value,
            "role": view.role.value,
            "player_count": view.player_count,
            "spectator_count": view.spectator_count,
            "gameplay_started": view.gameplay_started,
        }
        if view.seat is not None:
            payload["seat"] = view.seat.value
            payload["color"] = self._seat_adapter.protocol_color(view.seat)
        if view.game_token is not None:
            payload["game_token"] = view.game_token
        if view.role is GameRole.SPECTATOR:
            payload["snapshot"] = view.snapshot
        if view.leave_deferred:
            payload["leave_deferred"] = True
        return OutgoingMessage(MessageType.ROOM_STATUS.value, payload)
