import asyncio
from types import SimpleNamespace

import pytest

from kongfu_chess.engine import GameSnapshot, MoveResult, PieceSnapshot
from kongfu_chess.server import (
    BoardCoordinate,
    GameplayCommandService,
    GameplayError,
    GameplayRequest,
    GameSessionRegistry,
    SessionCommandType,
    build_game_session,
)


class FakeAuth:
    def __init__(self, user_id=1):
        self.user_id = user_id

    def validate_auth_token(self, _token, *, now_ms):
        return SimpleNamespace(user_id=self.user_id)


class FakeTokens:
    def __init__(self, *, user_id=1, role="PLAYER", color="w", valid=True):
        self.record = SimpleNamespace(user_id=user_id, role=role, color=color)
        self.valid = valid

    def verify_game(self, _token, *, game_id, now_ms):
        return self.record if self.valid else None


class FakeEngine:
    def __init__(self, *, piece_id=7, token="wP", row=1, col=4, game_over=False):
        self.current_snapshot = GameSnapshot(
            board_width=8,
            board_height=8,
            game_over=game_over,
            pieces=(PieceSnapshot(row, col, token, piece_id),),
        )
        self.move_calls = []
        self.jump_calls = []

    def snapshot(self):
        return self.current_snapshot

    def request_move(self, from_row, from_col, to_row, to_col):
        self.move_calls.append((from_row, from_col, to_row, to_col))
        return MoveResult(True, "ok")

    def request_jump(self, from_row, from_col):
        self.jump_calls.append((from_row, from_col))
        return MoveResult(True, "ok")


def request(*, piece_id=7, expected=(1, 4), target=(3, 4)):
    return GameplayRequest(
        auth_token="auth",
        game_token="game-token",
        game_id="game-1",
        piece_id=piece_id,
        expected_from=BoardCoordinate(*expected),
        target=BoardCoordinate(*target),
    )


async def system(engine, *, auth=None, tokens=None):
    session = build_game_session(
        "game-1",
        engine,
        initial_sequence=0,
        request_cache_size=16,
    )
    session.start()
    registry = GameSessionRegistry()
    registry.register(session)
    service = GameplayCommandService(
        auth or FakeAuth(),
        tokens or FakeTokens(),
        registry,
    )
    return service, session


def test_valid_move_is_translated_inside_queue_and_increments_sequence():
    async def scenario():
        engine = FakeEngine()
        service, session = await system(engine)
        result = await service.submit(
            SessionCommandType.MOVE, "request-1", request(), now_ms=1000
        )
        await session.close()
        return engine, result

    engine, result = asyncio.run(scenario())

    assert result.accepted is True
    assert result.code == "ok"
    assert result.sequence == 1
    assert engine.move_calls == [(1, 4, 3, 4)]


@pytest.mark.parametrize(
    ("engine", "command_request", "expected_code"),
    [
        (FakeEngine(row=2), request(), "stale_client_state"),
        (FakeEngine(token="bP"), request(), "forbidden_piece"),
        (FakeEngine(), request(piece_id=999), "invalid_piece"),
        (FakeEngine(game_over=True), request(), "game_over"),
    ],
)
def test_live_snapshot_rejections_do_not_mutate_or_advance_sequence(
    engine, command_request, expected_code
):
    async def scenario():
        service, session = await system(engine)
        result = await service.submit(
            SessionCommandType.MOVE,
            "request-1",
            command_request,
            now_ms=1000,
        )
        await session.close()
        return result

    result = asyncio.run(scenario())

    assert result.accepted is False
    assert result.code == expected_code
    assert result.sequence == 0
    assert engine.move_calls == []


def test_duplicate_request_id_executes_engine_only_once():
    async def scenario():
        engine = FakeEngine()
        service, session = await system(engine)
        first = await service.submit(
            SessionCommandType.MOVE, "same-request", request(), now_ms=1000
        )
        second = await service.submit(
            SessionCommandType.MOVE, "same-request", request(target=(4, 4)), now_ms=1001
        )
        await session.close()
        return engine, first, second

    engine, first, second = asyncio.run(scenario())

    assert first is second
    assert first.sequence == 1
    assert engine.move_calls == [(1, 4, 3, 4)]


def test_jump_requires_in_place_target_and_preserves_engine_api():
    async def scenario():
        engine = FakeEngine()
        service, session = await system(engine)
        invalid = await service.submit(
            SessionCommandType.JUMP,
            "jump-invalid",
            request(target=(2, 4)),
            now_ms=1000,
        )
        valid = await service.submit(
            SessionCommandType.JUMP,
            "jump-valid",
            request(target=(1, 4)),
            now_ms=1001,
        )
        await session.close()
        return engine, invalid, valid

    engine, invalid, valid = asyncio.run(scenario())

    assert invalid.code == "invalid_field"
    assert invalid.sequence == 0
    assert valid.accepted is True
    assert valid.sequence == 1
    assert engine.jump_calls == [(1, 4)]


def test_game_token_must_belong_to_authenticated_player():
    async def scenario():
        service, session = await system(FakeEngine(), tokens=FakeTokens(user_id=2))
        with pytest.raises(GameplayError) as raised:
            await service.submit(
                SessionCommandType.MOVE, "request-1", request(), now_ms=1000
            )
        await session.close()
        return raised.value

    error = asyncio.run(scenario())
    assert error.code.value == "forbidden"
