from kongfu_chess.engine.game_engine import GameEngine
from kongfu_chess.engine.reasons import MoveReason
from kongfu_chess.game import Game
from kongfu_chess.model.board import Board
from kongfu_chess.model.events import GameOverEvent
from kongfu_chess.model.game_state import GameState
from kongfu_chess.model.piece_state import PieceState
from kongfu_chess.realtime.movement_policy import MovementPolicy
from kongfu_chess.rules import RuleEngine


def make_engine(rows, *, move_durations=None, movement_policy=None):
    board = Board(rows)
    state = GameState(board=board)
    engine = GameEngine(
        board,
        state,
        RuleEngine(),
        move_durations=move_durations,
        movement_policy=movement_policy,
    )
    return board, state, engine


def test_airborne_piece_leaves_source_but_remains_in_snapshot():
    board, _, engine = make_engine(
        [
            ["wN", ".", "."],
            [".", ".", "."],
            [".", ".", "."],
        ],
        move_durations={"N": 1000},
    )
    knight_id = board.get_cell(0, 0).piece_id

    result = engine.request_move(0, 0, 1, 2)

    assert result.is_accepted is True
    assert board.get_cell(0, 0) is None
    moving = next(piece for piece in engine.snapshot().pieces if piece.piece_id == knight_id)
    assert moving.state == PieceState.MOVING
    assert (moving.row, moving.col) == (0, 0)


def test_enemy_may_occupy_vacated_source_without_capturing_airborne_piece():
    board, state, engine = make_engine(
        [
            ["wN", ".", "bR"],
            [".", ".", "."],
            [".", ".", "."],
        ],
        move_durations={"N": 1000, "R": 250},
    )
    knight_id = board.get_cell(0, 0).piece_id

    assert engine.request_move(0, 0, 1, 2).is_accepted is True
    assert engine.request_move(0, 2, 0, 0).is_accepted is True
    engine.wait(500)

    assert board.get_cell(0, 0).token == "bR"
    assert all(item.piece_id != knight_id for item in state.captured_pieces)

    engine.wait(500)
    assert board.get_cell(1, 2).piece_id == knight_id


def test_airborne_piece_captures_current_enemy_on_landing():
    board, state, engine = make_engine(
        [
            ["wN", ".", "."],
            [".", ".", "bR"],
            [".", ".", "."],
        ],
        move_durations={"N": 1000},
    )
    knight_id = board.get_cell(0, 0).piece_id
    captured_id = board.get_cell(1, 2).piece_id

    assert engine.request_move(0, 0, 1, 2).is_accepted is True
    engine.wait(1000)

    assert board.get_cell(1, 2).piece_id == knight_id
    assert state.captured_pieces[-1].piece_id == captured_id
    assert dict(state.score_by_color) == {"w": 5, "b": 0}


def test_airborne_king_capture_marks_game_over_and_publishes_event():
    board, state, engine = make_engine(
        [
            ["wN", ".", "."],
            [".", ".", "bK"],
            [".", ".", "."],
        ],
        move_durations={"N": 1000},
    )
    events = []

    class Subscriber:
        def handle(self, event):
            events.append(event)

    engine.subscribe(GameOverEvent, Subscriber())
    assert engine.request_move(0, 0, 1, 2).is_accepted is True
    engine.wait(1000)

    assert state.is_game_over is True
    assert events == [
        GameOverEvent(
            winning_color="w",
            captured_piece_id=state.captured_pieces[-1].piece_id,
        )
    ]


def test_friendly_piece_cannot_target_reserved_landing_cell():
    board, _, engine = make_engine(
        [
            ["wN", ".", "."],
            ["wR", ".", "."],
            [".", ".", "."],
        ],
        move_durations={"N": 1000, "R": 100},
    )

    assert engine.request_move(0, 0, 1, 2).is_accepted is True
    result = engine.request_move(1, 0, 1, 2)

    assert result.is_accepted is False
    assert result.reason == MoveReason.DESTINATION_RESERVED
    assert board.get_cell(1, 0).token == "wR"


def test_friendly_route_stops_before_reserved_landing_cell():
    board, _, engine = make_engine(
        [
            ["wN", ".", ".", "."],
            ["wR", ".", ".", "."],
            [".", ".", ".", "."],
        ],
        move_durations={"N": 1000, "R": 100},
    )

    assert engine.request_move(0, 0, 1, 2).is_accepted is True
    assert engine.request_move(1, 0, 1, 3).is_accepted is True
    engine.wait(300)

    assert board.get_cell(1, 1).token == "wR"
    assert board.get_cell(1, 2) is None


def test_existing_friendly_route_has_priority_over_later_landing_reservation():
    board, _, engine = make_engine(
        [
            ["wN", ".", ".", "."],
            ["wR", ".", ".", "."],
            [".", ".", ".", "."],
        ],
        move_durations={"N": 1000, "R": 100},
    )

    assert engine.request_move(1, 0, 1, 3).is_accepted is True
    result = engine.request_move(0, 0, 1, 2)

    assert result.is_accepted is False
    assert result.reason == MoveReason.DESTINATION_RESERVED
    assert board.get_cell(0, 0).token == "wN"


def test_landing_releases_reservation():
    _, _, engine = make_engine(
        [
            ["wN", ".", "."],
            [".", ".", "."],
            [".", ".", "."],
        ],
        move_durations={"N": 1000},
    )

    assert engine.request_move(0, 0, 1, 2).is_accepted is True
    assert engine.arbiter.reservation_at((1, 2)) is not None

    engine.wait(1000)

    assert engine.arbiter.reservation_at((1, 2)) is None


def test_opposing_airborne_pieces_may_target_the_same_landing_cell():
    board, state, engine = make_engine(
        [
            ["wN", ".", "."],
            [".", ".", "."],
            ["bN", ".", "."],
        ],
        move_durations={"N": 1000},
    )
    white_id = board.get_cell(0, 0).piece_id
    black_id = board.get_cell(2, 0).piece_id

    assert engine.request_move(0, 0, 1, 2).is_accepted is True
    assert engine.request_move(2, 0, 1, 2).is_accepted is True
    engine.wait(1000)

    assert board.get_cell(1, 2).piece_id == black_id
    assert state.captured_pieces[-1].piece_id == white_id


def test_custom_policy_can_make_another_piece_type_airborne():
    policy = MovementPolicy(airborne_piece_types={"K"})
    board, _, engine = make_engine(
        [["wK", "."]],
        move_durations={"K": 1000},
        movement_policy=policy,
    )

    assert engine.request_move(0, 0, 0, 1).is_accepted is True
    assert board.get_cell(0, 0) is None


def test_game_facade_forwards_custom_movement_policy():
    policy = MovementPolicy(airborne_piece_types={"K"})
    board = Board([["wK", "."]])
    game = Game(
        board,
        move_durations={"K": 1000},
        movement_policy=policy,
    )

    assert game.request_move(0, 0, 0, 1).is_accepted is True
    assert board.get_cell(0, 0) is None


def test_grounded_piece_keeps_existing_mid_flight_occupancy_behavior():
    board, _, engine = make_engine(
        [["wK", "."]],
        move_durations={"K": 1000},
    )

    assert engine.request_move(0, 0, 0, 1).is_accepted is True
    engine.wait(999)

    assert board.get_cell(0, 0).token == "wK"
