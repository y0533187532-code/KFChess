import pytest

from kongfu_chess.engine import EngineSettings, GameEngine
from kongfu_chess.model.board import Board
from kongfu_chess.model.game_state import GameState
from kongfu_chess.rules import RuleEngine


class FixedScorePolicy:
    def __init__(self, points):
        self._points = points

    def points_for(self, _captured_piece):
        return self._points


class RecordingMotionOutcomes:
    def __init__(self):
        self.executed_moves = []

    def execute_move(self, move):
        self.executed_moves.append(move)


def test_engine_settings_merge_partial_overrides_and_are_immutable():
    settings = EngineSettings.from_overrides(move_durations={"R": 25})

    assert settings.move_duration_for("R") == 25
    assert settings.move_duration_for("K") > 0
    with pytest.raises(TypeError):
        settings.move_durations_ms["R"] = 50


def test_engine_accepts_polymorphic_score_policy():
    board = Board([["wR", "bP"]])
    state = GameState(board)
    engine = GameEngine(
        board,
        state,
        RuleEngine(),
        move_durations={"R": 10},
        score_policy=FixedScorePolicy(points=42),
    )

    engine.request_move(0, 0, 0, 1)
    engine.wait(10)

    assert state.score_by_color["w"] == 42


def test_snapshot_does_not_expose_mutable_score_state():
    board = Board([["wK"]])
    state = GameState(board)
    snapshot = GameEngine(board, state, RuleEngine()).snapshot()

    with pytest.raises(TypeError):
        snapshot.score_by_color["w"] = 100
    assert state.score_by_color["w"] == 0


def test_engine_delegates_motion_outcomes_to_injected_handler():
    board = Board([["wK", "."]])
    state = GameState(board)
    outcomes = RecordingMotionOutcomes()
    engine = GameEngine(
        board,
        state,
        RuleEngine(),
        motion_outcomes=outcomes,
    )
    motion = {"from": (0, 0), "to": (0, 1), "color": "w"}

    engine.execute_move(motion)

    assert outcomes.executed_moves == [motion]
