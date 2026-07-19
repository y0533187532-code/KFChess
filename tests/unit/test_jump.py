"""Airborne jump tests — scheduling, mid-air state, landing, and parallel interaction."""

import io

import pytest

from kongfu_chess.config import (
    DEFAULT_JUMP_DURATION_MS,
    DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE,
)
from kongfu_chess.engine.game_engine import GameEngine
from kongfu_chess.engine.types import MoveResult
from kongfu_chess.game import Game
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.realtime import (
    RealTimeArbiter,
    collect_airborne_jumps,
    is_captured_by_airborne_jump,
    is_jump_motion,
)
from kongfu_chess.rules import RuleEngine
from kongfu_chess.texttests.script_runner import ScriptRunner


def make_game(rows):
    board = Board(rows)
    return board, Game(board)


def make_engine(rows):
    board = Board(rows)
    state = GameState(board=board)
    engine = GameEngine(board, state, RuleEngine())
    return board, state, engine


def finish_jump(engine, ms=None):
    engine.wait(ms if ms is not None else DEFAULT_JUMP_DURATION_MS)


# --- Unit: airborne_jump helpers ---


def test_is_jump_motion_detects_jump_flag():
    assert is_jump_motion({"jump": True}) is True
    assert is_jump_motion({"route": [(0, 1)]}) is False


def test_is_captured_by_airborne_jump_when_enemy_lands_on_jumper_cell():
    travel = {"from": (0, 1), "to": (0, 0), "color": "b"}
    jumps = [{"from": (0, 0), "color": "w", "jump": True, "remaining": 500}]
    assert is_captured_by_airborne_jump(travel, jumps) is True


def test_collect_airborne_jumps_includes_active_jumps():
    jump = {"jump": True, "remaining": 100, "order": 0}
    active = [jump]
    assert collect_airborne_jumps([], active) == [jump]


# --- GameEngine: valid / invalid jump ---


def test_request_jump_schedules_airborne_motion():
    board, _, engine = make_engine([["wK"]])
    result = engine.request_jump(0, 0)
    assert result == MoveResult(is_accepted=True, reason="ok")
    assert len(engine.active_moves) == 1
    assert is_jump_motion(engine.active_moves[0])
    assert board.get_cell(0, 0).token == "wK"


def test_request_jump_rejects_game_over():
    board, state, engine = make_engine([["wK"]])
    state.mark_game_over()
    result = engine.request_jump(0, 0)
    assert result.reason == "game_over"
    assert engine.active_moves == []


def test_request_jump_rejects_empty_source():
    board, _, engine = make_engine([["."]])
    result = engine.request_jump(0, 0)
    assert result.reason == "empty_source"
    assert engine.active_moves == []


# --- Mid-air and landing ---


def test_jump_mid_air_keeps_piece_on_logical_board():
    board, _, engine = make_engine([["wK"]])
    engine.request_jump(0, 0)
    engine.wait(DEFAULT_JUMP_DURATION_MS // 2)
    assert board.get_cell(0, 0).token == "wK"
    assert engine.has_active_motion() is True


def test_jump_landing_removes_motion_without_moving_piece():
    board, _, engine = make_engine([["wK"]])
    engine.request_jump(0, 0)
    finish_jump(engine)
    assert board.get_cell(0, 0).token == "wK"
    assert engine.active_moves == []


def test_jump_landing_starts_rest_timer():
    board, _, engine = make_engine([["wK"]])
    piece_id = board.get_cell(0, 0).piece_id

    engine.request_jump(0, 0)
    finish_jump(engine)

    assert engine.arbiter.active_rests[piece_id] == DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE["K"]


def test_jump_landing_records_completed_move():
    board, state, engine = make_engine([["wK"]])
    piece_id = board.get_cell(0, 0).piece_id

    engine.request_jump(0, 0)
    finish_jump(engine)

    assert state.completed_moves[-1] == {
        "piece_id": piece_id,
        "token": "wK",
        "from": (0, 0),
        "requested_to": (0, 0),
        "actual_to": (0, 0),
        "reason": "jump",
    }


# --- Airborne capture ---


def test_enemy_arriving_at_airborne_origin_captures_jumper():
    board, _, engine = make_engine([["wK", "bR", "."]])
    engine.request_jump(0, 0)
    engine.request_move(0, 1, 0, 0)
    finish_jump(engine)
    assert board.get_cell(0, 0).token == "bR"
    assert board.get_cell(0, 1) is None


def test_enemy_diagonal_arrival_captures_airborne_jumper_and_logs_actual_resolution():
    board, state, engine = make_engine(
        [
            ["wK", ".", "."],
            [".", "bB", "."],
            [".", ".", "."],
        ]
    )
    white_piece_id = board.get_cell(0, 0).piece_id
    black_piece_id = board.get_cell(1, 1).piece_id

    assert engine.request_jump(0, 0) == MoveResult(is_accepted=True, reason="ok")
    assert engine.request_move(1, 1, 0, 0) == MoveResult(is_accepted=True, reason="ok")

    finish_jump(engine)

    assert board.get_cell(0, 0).token == "bB"
    assert board.get_cell(0, 0).piece_id == black_piece_id
    assert board.get_cell(1, 1) is None
    assert any(piece.piece_id == white_piece_id for piece, _, _ in state.captured_pieces)
    assert not any(is_jump_motion(move) and move["from"] == (0, 0) for move in engine.active_moves)
    assert engine.snapshot().score_by_color == {"w": 0, "b": 0}

    event = engine.snapshot().completed_moves[-1]
    assert event.piece_id == black_piece_id
    assert event.from_pos == (1, 1)
    assert event.requested_to == (0, 0)
    assert event.actual_to == (0, 0)
    assert event.reason == "capture"


def test_jumper_lands_after_enemy_arrival_and_captures_enemy():
    board, state, engine = make_engine(
        [
            ["wK", "."],
            [".", "bB"],
        ]
    )
    white_piece_id = board.get_cell(0, 0).piece_id
    black_piece_id = board.get_cell(1, 1).piece_id

    assert engine.request_move(1, 1, 0, 0) == MoveResult(
        is_accepted=True,
        reason="ok",
    )
    assert engine.request_jump(0, 0) == MoveResult(is_accepted=True, reason="ok")

    finish_jump(engine)

    assert board.get_cell(0, 0).token == "wK"
    assert board.get_cell(0, 0).piece_id == white_piece_id
    assert board.get_cell(1, 1) is None
    assert any(piece.piece_id == black_piece_id for piece, _, _ in state.captured_pieces)
    assert engine.snapshot().score_by_color == {"w": 3, "b": 0}


def test_snapshot_keeps_airborne_jumper_visible_above_enemy_on_same_cell():
    board = Board(
        [
            ["wK", "."],
            [".", "bB"],
        ]
    )
    state = GameState(board=board)
    engine = GameEngine(board, state, RuleEngine(), jump_duration_ms=2000)
    white_piece_id = board.get_cell(0, 0).piece_id
    black_piece_id = board.get_cell(1, 1).piece_id

    engine.request_move(1, 1, 0, 0)
    engine.request_jump(0, 0)
    engine.wait(DEFAULT_JUMP_DURATION_MS)

    pieces = {piece.piece_id: piece for piece in engine.snapshot().pieces}

    assert pieces[white_piece_id].token == "wK"
    assert pieces[white_piece_id].state == "jump"
    assert pieces[white_piece_id].row == 0
    assert pieces[white_piece_id].col == 0
    assert pieces[black_piece_id].token == "bB"
    assert pieces[black_piece_id].state != "jump"
    assert pieces[black_piece_id].row == 0
    assert pieces[black_piece_id].col == 0


# --- Parallel movement interaction ---


def test_jump_allowed_while_enemy_travel_is_in_flight():
    board, _, engine = make_engine([["wK", ".", "bR"]])
    engine.request_move(0, 2, 0, 0)
    result = engine.request_jump(0, 0)
    assert result.is_accepted is True
    assert len(engine.active_moves) == 2
    assert any(is_jump_motion(m) for m in engine.active_moves)


def test_jump_allowed_while_enemy_en_route_to_same_cell():
    board, game = make_game([["wK", ".", "bR"]])
    game.handle_click(250, 50)
    game.handle_click(50, 50)
    game.handle_click(50, 50)
    game.handle_click(50, 50)
    assert len(game._active_moves) == 2
    assert any(is_jump_motion(m) for m in game._active_moves)


def test_jump_completes_with_piece_still_on_original_cell():
    board, game = make_game([["wK"]])
    game.handle_click(50, 50)
    game.handle_click(50, 50)
    finish_jump(game.engine)
    assert board.get_cell(0, 0).token == "wK"
    assert not game._active_moves


# --- Controller + command integration ---


def test_same_cell_reclick_starts_airborne_jump():
    board, game = make_game([["wK"]])
    game.handle_click(50, 50)
    game.handle_click(50, 50)
    assert len(game._active_moves) == 1
    move = game._active_moves[0]
    assert is_jump_motion(move)
    assert move["from"] == (0, 0)
    assert move["remaining"] == DEFAULT_JUMP_DURATION_MS


def test_moving_piece_cannot_jump_via_controller():
    board, game = make_game([["wK", "."]])
    game.handle_click(50, 50)
    game.handle_click(150, 50)
    game.handle_click(150, 150)
    game._selected = (0, 0)
    game.handle_click(50, 50)
    assert len(game._active_moves) == 1
    assert not is_jump_motion(game._active_moves[0])


def test_jump_command_starts_airborne_jump():
    board = Board([["wK"]])
    game = Game(board)
    stdout = io.StringIO()
    ScriptRunner(game, board, stdout).run(["jump 50 50", "wait 1000"])
    assert board.get_cell(0, 0).token == "wK"
    assert not game._active_moves


def test_arbiter_complete_jump_does_not_touch_board():
    board, _, engine = make_engine([["wK"]])
    arbiter = RealTimeArbiter(engine)
    jump = arbiter.schedule_jump((0, 0), 1000, "w")
    before = board.render_rows()
    arbiter._complete_jump(jump)
    assert board.render_rows() == before
    assert arbiter.active_moves == []
