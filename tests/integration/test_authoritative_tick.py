import asyncio
from types import MappingProxyType, SimpleNamespace

from kongfu_chess.config import DEFAULT_MOVE_DURATION_MS
from kongfu_chess.engine.game_engine import GameEngine
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.model.piece_state import PieceState
from kongfu_chess.persistence import (
    AuthSessionRepository,
    GameLifecycleRepository,
    GameTokenRepository,
    MatchRepository,
    SqliteDatabase,
    TokenService,
    UserRepository,
)
from kongfu_chess.rules import RuleEngine
from kongfu_chess.server import (
    AuthService,
    EloService,
    GameLifecycleService,
    PasswordHasher,
    PlayerSeat,
    SessionCommand,
    SessionCommandType,
    build_game_session,
    standard_starting_board,
)
from kongfu_chess.server import (
    PLAY_GAME_MODE,
    PlayMatch,
    PlaySeat,
)


KING_MOVE_MS = DEFAULT_MOVE_DURATION_MS["K"]


def make_engine(rows):
    board = Board(rows)
    state = GameState(board=board)
    return GameEngine(board, state, RuleEngine())


def tick_command(interval_ms: int = 50):
    return SessionCommand(
        kind=SessionCommandType.TICK.value,
        request_id=None,
        payload=MappingProxyType({"interval_ms": interval_ms}),
    )


def move_command(*, piece_id, seat, expected_from, target, request_id="move-1"):
    return SessionCommand(
        kind=SessionCommandType.MOVE.value,
        request_id=request_id,
        payload=MappingProxyType(
            {
                "seat": seat,
                "piece_id": piece_id,
                "expected_from": SimpleNamespace(row=expected_from[0], col=expected_from[1]),
                "target": SimpleNamespace(row=target[0], col=target[1]),
            }
        ),
    )


def test_tick_advances_motion_without_client_command():
    async def scenario():
        engine = make_engine([["wK", "."]])
        piece_id = engine.snapshot().pieces[0].piece_id
        session = build_game_session(
            "game-1",
            engine,
            initial_sequence=0,
            request_cache_size=8,
            tick_interval_ms=50,
        )
        session.start()

        move_result = await session.submit(
            move_command(
                piece_id=piece_id,
                seat=PlayerSeat.FIRST_PLAYER,
                expected_from=(0, 0),
                target=(0, 1),
            )
        )
        assert move_result.accepted is True

        ticks = (KING_MOVE_MS // 50) + 2
        for _ in range(ticks):
            await session.submit(tick_command())

        arrived = next(item for item in engine.snapshot().pieces if item.piece_id == piece_id)
        assert arrived.row == 0 and arrived.col == 1
        assert arrived.state is PieceState.RESTING

    asyncio.run(scenario())


def test_tick_skipped_when_idle():
    async def scenario():
        engine = make_engine([["wK", "."]])
        session = build_game_session(
            "game-1",
            engine,
            initial_sequence=0,
            request_cache_size=8,
        )
        session.start()

        result = await session.submit(tick_command())

        assert result.accepted is True
        assert session.sequence == 0

    asyncio.run(scenario())


def test_tick_paused_during_reconnect():
    async def scenario():
        engine = make_engine([["wK", "."]])
        engine.request_move(0, 0, 0, 1)
        session = build_game_session(
            "game-1",
            engine,
            initial_sequence=0,
            request_cache_size=8,
        )
        session.start()
        session.pause()

        result = await session.submit(tick_command())

        assert result.accepted is False
        assert result.code == "game_paused"

    asyncio.run(scenario())


def test_bootstrap_registers_session_on_match(tmp_path):
    async def scenario():
        config = SimpleNamespace(
            timing=SimpleNamespace(tick_interval_ms=50, reconnect_grace_seconds=20),
            network=SimpleNamespace(initial_sequence=0, request_cache_size=4096),
        )
        database = SqliteDatabase(tmp_path / "bootstrap.sqlite3", busy_timeout_ms=1000)
        database.migrate()
        users = UserRepository(database, username_min_length=3, username_max_length=20)
        tokens = TokenService(
            AuthSessionRepository(database), GameTokenRepository(database), token_bytes=32
        )
        auth = AuthService(
            users,
            tokens,
            PasswordHasher(salt_bytes=16, n=1024, r=8, p=1, hash_bytes=32),
            password_min_length=6,
            initial_rating=1200,
            auth_token_ttl_seconds=600,
        )
        first = auth.register(
            username="White",
            password="secret7",
            email="white@example.test",
            phone="0501234567",
            now_ms=1000,
        )
        second = auth.register(
            username="Black",
            password="secret7",
            email="black@example.test",
            phone="0501234568",
            now_ms=1000,
        )
        lifecycle_repo = GameLifecycleRepository(database)
        lifecycle, registry, factory = GameLifecycleService.with_runtime(
            auth,
            tokens,
            lifecycle_repo,
            users,
            MatchRepository(database),
            EloService(scale=400, k_factor=32, rating_floor=100),
            config,
        )
        match = PlayMatch(
            "game-bootstrap",
            (
                PlaySeat(
                    first.user_id,
                    "White",
                    1200,
                    PlayerSeat.FIRST_PLAYER,
                    "white-token",
                ),
                PlaySeat(
                    second.user_id,
                    "Black",
                    1200,
                    PlayerSeat.SECOND_PLAYER,
                    "black-token",
                ),
            ),
            1000,
            PLAY_GAME_MODE,
        )

        lifecycle.register_play_match(match, now_ms=1000)

        session = registry.get("game-bootstrap")
        assert session is not None

        result = await session.submit(
            SessionCommand(
                kind=SessionCommandType.SNAPSHOT.value,
                request_id="snapshot-1",
            )
        )
        payload = result.payload
        assert payload["board_width"] == 8
        assert payload["board_height"] == 8
        assert len(payload["pieces"]) == 32
        factory._tick_scheduler.stop("game-bootstrap")

    asyncio.run(scenario())


def test_pre_command_sync_before_move():
    async def scenario():
        clock = {"now": 0}

        def clock_ms():
            return clock["now"]

        engine = make_engine([["wK", ".", "wR", "."]])
        king_id = engine.snapshot().pieces[0].piece_id
        rook_id = engine.snapshot().pieces[1].piece_id
        session = build_game_session(
            "game-1",
            engine,
            initial_sequence=0,
            request_cache_size=8,
            tick_interval_ms=50,
            clock_ms=clock_ms,
        )
        session.start()

        await session.submit(
            move_command(
                piece_id=king_id,
                seat=PlayerSeat.FIRST_PLAYER,
                expected_from=(0, 0),
                target=(0, 1),
            )
        )
        clock["now"] = 250

        await session.submit(
            move_command(
                piece_id=rook_id,
                seat=PlayerSeat.FIRST_PLAYER,
                expected_from=(0, 2),
                target=(0, 3),
                request_id="move-2",
            )
        )

        king = next(item for item in engine.snapshot().pieces if item.piece_id == king_id)
        remaining_values = sorted(
            motion.remaining_ms for motion in engine.snapshot().active_motions
        )
        assert king.col == 0
        assert remaining_values == [KING_MOVE_MS - 250, KING_MOVE_MS]
        assert len(engine.active_moves) == 2

    asyncio.run(scenario())


def test_standard_starting_board_matches_expected_dimensions():
    board = standard_starting_board()
    assert board.num_rows == 8
    assert board.num_cols == 8
