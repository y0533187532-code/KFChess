import asyncio
from types import MappingProxyType, SimpleNamespace

from kongfu_chess.config import DEFAULT_MOVE_DURATION_MS
from kongfu_chess.engine.game_engine import GameEngine
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.protocol import EnvelopePolicy, MessageType
from kongfu_chess.rules import RuleEngine
from kongfu_chess.server import (
    GameConnectionRegistry,
    GameSessionRegistry,
    PlayerSeat,
    SessionCommand,
    SessionCommandType,
    SnapshotPushService,
    build_game_session,
)


KING_MOVE_MS = DEFAULT_MOVE_DURATION_MS["K"]
POLICY = EnvelopePolicy("1.0", 4096, 64, 64)


class RecordingGateway:
    def __init__(self):
        self.messages: list[tuple[str, object]] = []

    async def broadcast(self, game_id, outgoing):
        self.messages.append((game_id, outgoing))


def make_engine(rows):
    board = Board(rows)
    state = GameState(board=board)
    return GameEngine(board, state, RuleEngine())


def move_command(*, piece_id, expected_from, target, request_id="move-1"):
    return SessionCommand(
        kind=SessionCommandType.MOVE.value,
        request_id=request_id,
        payload=MappingProxyType(
            {
                "seat": PlayerSeat.FIRST_PLAYER,
                "piece_id": piece_id,
                "expected_from": SimpleNamespace(
                    row=expected_from[0], col=expected_from[1]
                ),
                "target": SimpleNamespace(row=target[0], col=target[1]),
            }
        ),
    )


def tick_command(interval_ms: int = 50):
    return SessionCommand(
        kind=SessionCommandType.TICK.value,
        request_id=None,
        payload=MappingProxyType({"interval_ms": interval_ms}),
    )


def test_tick_pushes_state_update_to_bound_connection():
    async def scenario():
        engine = make_engine([["wK", "."]])
        piece_id = engine.snapshot().pieces[0].piece_id
        gateway = RecordingGateway()
        game_connections = GameConnectionRegistry()
        game_connections.bind("conn-1", "game-1", 1)
        push_service = SnapshotPushService(
            gateway,
            game_connections,
            POLICY,
            clock_ms=lambda: 1000,
        )

        async def on_sequence_changed(game_id, sequence, payload):
            await push_service.notify(game_id, sequence, payload)

        session = build_game_session(
            "game-1",
            engine,
            initial_sequence=0,
            request_cache_size=8,
            on_sequence_changed=on_sequence_changed,
        )
        session.start()

        await session.submit(
            move_command(
                piece_id=piece_id,
                expected_from=(0, 0),
                target=(0, 1),
            )
        )
        assert len(gateway.messages) == 1
        assert gateway.messages[0][1].payload["sequence"] == 1

        ticks = (KING_MOVE_MS // 50) + 2
        for _ in range(ticks):
            await session.submit(tick_command())

        assert len(gateway.messages) >= 1
        game_id, outgoing = gateway.messages[-1]
        assert game_id == "game-1"
        assert outgoing.type == MessageType.STATE_UPDATE.value
        assert outgoing.payload["sequence"] >= 1
        assert outgoing.payload["snapshot"]["board_width"] == 2

    asyncio.run(scenario())


def test_snapshot_push_service_skips_payload_without_snapshot():
    async def scenario():
        gateway = RecordingGateway()
        push_service = SnapshotPushService(
            gateway,
            GameConnectionRegistry(),
            POLICY,
            clock_ms=lambda: 1000,
        )

        await push_service.notify("game-1", 1, {"piece_id": 3})

        assert gateway.messages == []

    asyncio.run(scenario())
