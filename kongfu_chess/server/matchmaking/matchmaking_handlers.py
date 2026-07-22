"""Protocol handlers for authenticated ranked Play matchmaking."""

from __future__ import annotations

from ...protocol import MessageType, ProtocolError, ProtocolErrorCode
from ..app.routing import OutgoingMessage
from ..auth.auth_service import AuthError
from ..core.chess_compatibility import CHESS_SEAT_ADAPTER
from ..core.event_logger import ServerEventLogger
from ..core.game_mode import GameRole, SeatBoundaryAdapter
from .matchmaking_service import MatchmakingError, MatchmakingStatus


class MatchmakingHandlers:
    def __init__(
        self,
        matchmaking_service,
        *,
        clock_ms,
        seat_adapter: SeatBoundaryAdapter = CHESS_SEAT_ADAPTER,
        events: ServerEventLogger | None = None,
    ):
        self._matchmaking_service = matchmaking_service
        self._clock_ms = clock_ms
        self._seat_adapter = seat_adapter
        self._events = events or ServerEventLogger(None)

    def register_routes(self, router) -> None:
        router.register(MessageType.PLAY_QUEUE_JOIN.value, self.join)
        router.register(MessageType.PLAY_QUEUE_CANCEL.value, self.cancel)
        router.register(MessageType.PLAY_QUEUE_STATUS.value, self.status)

    def join(self, context) -> OutgoingMessage:
        auth_token = self._auth_token(context)
        outgoing = self._execute(
            lambda: self._status_message(
                self._matchmaking_service.join(
                    auth_token, now_ms=self._clock_ms()
                )
            )
        )
        self._log_queue_event(context, "matchmaking_join", outgoing)
        return outgoing

    def cancel(self, context) -> OutgoingMessage:
        auth_token = self._auth_token(context)
        return self._execute(
            lambda: self._status_message(
                self._matchmaking_service.cancel(
                    auth_token, now_ms=self._clock_ms()
                )
            )
        )

    def status(self, context) -> OutgoingMessage:
        auth_token = self._auth_token(context)
        return self._execute(
            lambda: self._status_message(
                self._matchmaking_service.status(
                    auth_token, now_ms=self._clock_ms()
                )
            )
        )

    @staticmethod
    def _auth_token(context) -> str:
        payload = context.envelope.payload
        if set(payload) != {"auth_token"} or not isinstance(
            payload.get("auth_token"), str
        ):
            raise ProtocolError(
                ProtocolErrorCode.INVALID_FIELD,
                "Matchmaking payload does not match its schema",
            )
        return payload["auth_token"]

    @classmethod
    def _execute(cls, action) -> OutgoingMessage:
        try:
            return action()
        except (AuthError, MatchmakingError) as exc:
            return OutgoingMessage(
                MessageType.COMMAND_RESULT.value,
                {"accepted": False, "code": exc.code.value},
            )

    def _status_message(self, status: MatchmakingStatus) -> OutgoingMessage:
        if status.state == "MATCH_FOUND":
            return self._match_found(status)
        if status.state == "TIMED_OUT":
            return OutgoingMessage(
                MessageType.MATCHMAKING_TIMEOUT.value,
                {
                    "accepted": False,
                    "code": ProtocolErrorCode.MATCHMAKING_TIMEOUT.value,
                    "state": "timed_out",
                    "user_id": status.user_id,
                },
            )

        payload = {
            "accepted": True,
            "code": "ok",
            "state": status.state.lower(),
            "user_id": status.user_id,
        }
        if status.ticket is not None:
            payload.update(
                {
                    "rating": status.ticket.rating,
                    "enqueued_at_ms": status.ticket.enqueued_at_ms,
                    "expires_at_ms": status.ticket.expires_at_ms,
                }
            )
        return OutgoingMessage(MessageType.PLAY_QUEUE_STATUS.value, payload)

    def _match_found(self, status: MatchmakingStatus) -> OutgoingMessage:
        match = status.match
        if match is None:
            raise ValueError("MATCH_FOUND status requires a match view")
        self._events.event(
            "match_created",
            user_id=status.user_id,
            game_id=match.game_id,
            ranked=match.ranked,
        )
        return OutgoingMessage(
            MessageType.PLAY_MATCH_FOUND.value,
            {
                "accepted": True,
                "code": "ok",
                "state": "match_found",
                "game_id": match.game_id,
                "game_token": match.game_token,
                "role": GameRole.PLAYER.value,
                "seat": match.seat.value,
                "color": self._seat_adapter.protocol_color(match.seat),
                "ranked": match.ranked,
                "mode": match.mode,
                "opponent": {
                    "user_id": match.opponent_user_id,
                    "username": match.opponent_username,
                    "rating": match.opponent_rating,
                },
            },
        )

    def _log_queue_event(
        self, context, event_prefix: str, outgoing: OutgoingMessage
    ) -> None:
        payload = outgoing.payload
        fields = {
            "request_id": context.envelope.request_id,
            "connection_id": context.connection_id,
            "accepted": payload.get("accepted"),
        }
        if payload.get("code"):
            fields["code"] = payload["code"]
        if payload.get("user_id") is not None:
            fields["user_id"] = payload["user_id"]
        if payload.get("state"):
            fields["state"] = payload["state"]
        if payload.get("game_id"):
            fields["game_id"] = payload["game_id"]
        if payload.get("state") == "timed_out":
            self._events.event("matchmaking_timeout", **fields)
            return
        if payload.get("state") == "match_found":
            return
        self._events.event(event_prefix, **fields)
