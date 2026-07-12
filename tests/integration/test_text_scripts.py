from pathlib import Path

import pytest

from tests.integration.kfc_runner import parse_kfc, run_kfc_script

SCRIPTS_DIR = Path(__file__).parent / "scripts"
MOVEMENT_SCRIPTS = {
    "02_click_to_move.kfc": {
        "piece": "wK",
        "source": (0, 0),
        "destination": (1, 1),
        "print_count": 2,
    },
    "03_rook_moves.kfc": {
        "piece": "wR",
        "source": (0, 1),
        "destination": (2, 1),
        "print_count": 4,
    },
}


@pytest.mark.parametrize(
    "script_path",
    sorted(SCRIPTS_DIR.glob("*.kfc")),
    ids=lambda path: path.name,
)
def test_kfc_script_matches_print_board_expectations(script_path):
    run_kfc_script(script_path)


def test_parse_kfc_collects_multiple_print_board_expectations():
    text = Path(SCRIPTS_DIR / "03_rook_moves.kfc").read_text(encoding="utf-8")
    board_rows, commands, expectations = parse_kfc(text)
    assert board_rows == [[".", "wR", "."], [".", ".", "."], [".", ".", "bK"]]
    assert "print board" in commands
    assert len(expectations) == 4
    assert expectations[0] == expectations[1] == expectations[2]
    assert expectations[-1] == [". . .", ". . .", ". wR bK"]


@pytest.mark.parametrize("script_name", MOVEMENT_SCRIPTS.keys())
def test_movement_script_uses_select_and_destination_clicks(script_name):
    text = Path(SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
    _, commands, _ = parse_kfc(text)
    clicks = [command for command in commands if command.startswith("click ")]
    assert len(clicks) == 2, f"{script_name} must use exactly two clicks"


@pytest.mark.parametrize("script_name", MOVEMENT_SCRIPTS.keys())
def test_movement_script_expectations_differ_before_and_after_arrival(script_name):
    text = Path(SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
    board_rows, _, expectations = parse_kfc(text)
    meta = MOVEMENT_SCRIPTS[script_name]
    assert len(expectations) == meta["print_count"]

    initial = [" ".join(row) for row in board_rows]
    final = expectations[-1]
    assert initial != final, f"{script_name} final board must differ from setup"

    pre_arrival = expectations[-2]
    assert pre_arrival != final, f"{script_name} must change board after full wait"


@pytest.mark.parametrize("script_name", MOVEMENT_SCRIPTS.keys())
def test_movement_script_would_fail_if_piece_never_moved(script_name):
    """Regression guard: wrong final expectation must not pass."""
    text = Path(SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
    board_rows, commands, expectations = parse_kfc(text)
    stale_final = expectations[0]
    expectations[-1] = stale_final

    import io

    from kongfu_chess.game import Game
    from kongfu_chess.io.board_parser import BoardParser
    from kongfu_chess.texttests.script_runner import ScriptRunner
    from tests.integration.kfc_runner import _split_print_outputs

    board = BoardParser().parse_rows(board_rows)
    game = Game(board)
    stdout = io.StringIO()
    ScriptRunner(game, board, stdout).run(commands)
    outputs = _split_print_outputs(stdout.getvalue(), expectations)

    with pytest.raises(AssertionError):
        assert outputs[-1] == expectations[-1]

