"""Authenticated network commands translated to the existing engine API."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from ..engine.reasons import MoveReason
from ..protocol import ProtocolErrorCode
from .chess_compatibility import CHESS_SEAT_ADAPTER
from .game_mode import GameRole, PlayerSeat, SeatBoundaryAdapter
from .game_session import (
    GameSession,
    HandlerResult,
    SessionCommand,
    SessionCommandType,
)


class GameplayError(ValueError):
    def __init__(self, code: ProtocolErrorCode):
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True)
class BoardCoordinate:
    row: int
    col: int


@dataclass(frozen=True)
class GameplayRequest:
    auth_token: str
    game_token: str
    game_id: str
    piece_id: int
    expected_from: BoardCoordinate
    target: BoardCoordinate


class GameSessionRegistry:
    """In-memory lookup for live authoritative game queues."""

    def __init__(self):
        self._sessions: dict[str, GameSession] = {}

    def register(self, session: GameSession) -> None:
        if session.game_id in self._sessions:
            raise ValueError("A game session is already registered for this game")
        self._sessions[session.game_id] = session

    def get(self, game_id: str) -> GameSession | None:
        return self._sessions.get(game_id)

    def remove(self, game_id: str) -> GameSession | None:
        return self._sessions.pop(game_id, None)


class GameplayCommandService:
    """Authenticate a request, authorize its game seat, then enqueue it."""

    def __init__(
        self,
        auth_service,
        token_service,
        sessions: GameSessionRegistry,
        *,
        seat_adapter: SeatBoundaryAdapter = CHESS_SEAT_ADAPTER,
    ):
        self._auth_service = auth_service
        self._token_service = token_service
        self._sessions = sessions
        self._seat_adapter = seat_adapter

    async def submit(
        self,
        kind: SessionCommandType,
        request_id: str,
        request: GameplayRequest,
        *,
        now_ms: int,
    ):
        if kind not in (SessionCommandType.MOVE, SessionCommandType.JUMP):
            raise GameplayError(ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE)
        principal = self._auth_service.validate_auth_token(
            request.auth_token, now_ms=now_ms
        )
        game_token = self._token_service.verify_game(
            request.game_token,
            game_id=request.game_id,
            now_ms=now_ms,
        )
        if game_token is None:
            raise GameplayError(ProtocolErrorCode.INVALID_TOKEN)
        if (
            game_token.user_id != principal.user_id
            or game_token.role != GameRole.PLAYER.value
            or game_token.color is None
        ):
            raise GameplayError(ProtocolErrorCode.FORBIDDEN)
        try:
            seat = self._seat_adapter.seat_for_color(game_token.color)
        except (TypeError, ValueError) as exc:
            raise GameplayError(ProtocolErrorCode.FORBIDDEN) from exc

        session = self._sessions.get(request.game_id)
        if session is None:
            raise GameplayError(ProtocolErrorCode.GAME_NOT_FOUND)
        return await session.submit(
            SessionCommand(
                kind=kind.value,
                request_id=request_id,
                payload=MappingProxyType(
                    {
                        "seat": seat,
                        "piece_id": request.piece_id,
                        "expected_from": request.expected_from,
                        "target": request.target,
                    }
                ),
            )
        )


class NetworkGameAdapter:
    """Inspect authoritative snapshots and invoke coordinate-based engine calls."""

    _REASON_CODES = MappingProxyType(
        {
            MoveReason.OK: "ok",
            MoveReason.GAME_OVER: ProtocolErrorCode.GAME_OVER.value,
            MoveReason.PIECE_IN_MOTION: ProtocolErrorCode.PIECE_BUSY.value,
            MoveReason.PIECE_RESTING: ProtocolErrorCode.PIECE_BUSY.value,
            MoveReason.OUTSIDE_BOARD: ProtocolErrorCode.OUTSIDE_BOARD.value,
            MoveReason.EMPTY_SOURCE: ProtocolErrorCode.EMPTY_SOURCE.value,
            MoveReason.FRIENDLY_DESTINATION: ProtocolErrorCode.FRIENDLY_DESTINATION.value,
            MoveReason.ILLEGAL_PIECE_MOVE: ProtocolErrorCode.ILLEGAL_PIECE_MOVE.value,
            MoveReason.PATH_BLOCKED: ProtocolErrorCode.PATH_BLOCKED.value,
            MoveReason.DESTINATION_RESERVED: ProtocolErrorCode.DESTINATION_RESERVED.value,
        }
    )

    def __init__(
        self,
        engine,
        *,
        seat_adapter: SeatBoundaryAdapter = CHESS_SEAT_ADAPTER,
    ):
        self._engine = engine
        self._seat_adapter = seat_adapter

    @property
    def handlers(self):
        return MappingProxyType(
            {
                SessionCommandType.MOVE.value: self.handle_move,
                SessionCommandType.JUMP.value: self.handle_jump,
            }
        )

    def handle_move(self, command: SessionCommand) -> HandlerResult:
        return self._handle(command, jump=False)

    def handle_jump(self, command: SessionCommand) -> HandlerResult:
        return self._handle(command, jump=True)

    def _handle(self, command: SessionCommand, *, jump: bool) -> HandlerResult:
        seat: PlayerSeat = command.payload["seat"]
        piece_id: int = command.payload["piece_id"]
        expected_from: BoardCoordinate = command.payload["expected_from"]
        target: BoardCoordinate = command.payload["target"]

        if jump and target != expected_from:
            return self._rejected(ProtocolErrorCode.INVALID_FIELD)

        snapshot = self._engine.snapshot()
        if snapshot.game_over:
            return self._rejected(ProtocolErrorCode.GAME_OVER)
        piece = next(
            (item for item in snapshot.pieces if item.piece_id == piece_id),
            None,
        )
        if piece is None:
            return self._rejected(ProtocolErrorCode.INVALID_PIECE)
        if piece.token[:1] != self._seat_adapter.protocol_color(seat):
            return self._rejected(ProtocolErrorCode.FORBIDDEN_PIECE)
        if (piece.row, piece.col) != (expected_from.row, expected_from.col):
            return HandlerResult(
                accepted=False,
                changed=False,
                code=ProtocolErrorCode.STALE_CLIENT_STATE.value,
                payload={
                    "piece_id": piece_id,
                    "actual_from": {"row": piece.row, "col": piece.col},
                },
            )

        if jump:
            result = self._engine.request_jump(expected_from.row, expected_from.col)
        else:
            result = self._engine.request_move(
                expected_from.row,
                expected_from.col,
                target.row,
                target.col,
            )
        code = self._REASON_CODES.get(
            result.reason, ProtocolErrorCode.INVALID_FIELD.value
        )
        return HandlerResult(
            accepted=result.is_accepted,
            changed=result.is_accepted,
            code=code,
            payload={"piece_id": piece_id},
        )

    @staticmethod
    def _rejected(code: ProtocolErrorCode) -> HandlerResult:
        return HandlerResult(False, False, code.value)


def build_game_session(
    game_id: str,
    engine,
    *,
    initial_sequence: int,
    request_cache_size: int,
    seat_adapter: SeatBoundaryAdapter = CHESS_SEAT_ADAPTER,
) -> GameSession:
    adapter = NetworkGameAdapter(engine, seat_adapter=seat_adapter)
    return GameSession(
        game_id,
        adapter.handlers,
        initial_sequence=initial_sequence,
        request_cache_size=request_cache_size,
    )
