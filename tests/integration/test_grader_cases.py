"""Regression tests mirroring the course grader inputs (tests 2-21).

Each case runs main.py as a subprocess with stdin redirected, matching
how the course grader invokes the program.
"""

import subprocess
import sys

import pytest

from tests.conftest import PROJECT_ROOT

MAIN_PY = PROJECT_ROOT / "main.py"


def run_main(raw_text):
    result = subprocess.run(
        [sys.executable, str(MAIN_PY)],
        input=raw_text,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode, result.stdout.strip(), result.stderr


def assert_output(raw_text, expected_lines, expected_exit=0):
    exit_code, stdout, stderr = run_main(raw_text)
    expected = (
        expected_lines
        if isinstance(expected_lines, str)
        else "\n".join(expected_lines)
    )
    assert exit_code == expected_exit, f"stderr: {stderr!r}"
    assert stdout == expected, f"got: {stdout!r}, expected: {expected!r}"


def test_grader_2_parse_rectangular_board_3x4():
    assert_output(
        "Board:\nwK . . bK\n. . . .\nwR . . bR\nCommands:\nprint board\n",
        ["wK . . bK", ". . . .", "wR . . bR"],
    )


def test_grader_3_parse_piece_tokens_and_colors():
    assert_output(
        "Board:\nwK . bQ\n. wN .\nbP . wR\nCommands:\nprint board\n",
        ["wK . bQ", ". wN .", "bP . wR"],
    )


def test_grader_4_reject_unknown_token():
    assert_output(
        "Board:\nwK xZ\n. .\nCommands:\n",
        "ERROR UNKNOWN_TOKEN",
        expected_exit=1,
    )


def test_grader_5_reject_row_width_mismatch():
    assert_output(
        "Board:\nwK . .\n. bK\nCommands:\n",
        "ERROR ROW_WIDTH_MISMATCH",
        expected_exit=1,
    )


def test_grader_6_select_piece_by_center_click():
    assert_output(
        " Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 150 150\n"
        "wait 1000\n"
        "print board\n",
        [". . .", ". wK .", ". . ."],
    )


def test_grader_7_click_empty_cell_does_not_select():
    assert_output(
        " Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 150 150\n"
        "click 250 250\n"
        "print board\n",
        ["wK . .", ". . .", ". . ."],
    )


def test_grader_8_click_outside_board_is_ignored():
    assert_output(
        " Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 350 50\n"
        "click -10 50\n"
        "print board\n",
        ["wK . .", ". . .", ". . ."],
    )


def test_grader_9_clicking_another_piece_replaces_selection():
    assert_output(
        " Board:\n"
        "wR . wK\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "click 250 150\n"
        "wait 1000\n"
        "print board\n",
        ["wR . .", ". . wK"],
    )


def test_grader_10_reject_unknown_token_with_print():
    assert_output(
        " Board:\n"
        "wK xZ\n"
        ". .\n"
        "Commands:\n"
        "print board\n",
        "ERROR UNKNOWN_TOKEN",
        expected_exit=1,
    )


def test_grader_11_reject_row_width_mismatch_with_print():
    assert_output(
        " Board:\n"
        "wK . .\n"
        ". bK\n"
        "Commands:\n"
        "print board\n",
        "ERROR ROW_WIDTH_MISMATCH",
        expected_exit=1,
    )


def test_grader_12_king_one_step_valid():
    assert_output(
        " Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 150 150\n"
        "wait 1000\n"
        "print board\n",
        [". . .", ". wK .", ". . ."],
    )


def test_grader_13_king_two_steps_invalid():
    assert_output(
        " Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 250\n"
        "wait 1000\n"
        "print board\n",
        ["wK . .", ". . .", ". . ."],
    )


def test_grader_14_rook_straight_valid():
    assert_output(
        " Board:\n"
        "wR . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 2000\n"
        "print board\n",
        [". . wR"],
    )


def test_grader_15_rook_diagonal_invalid():
    assert_output(
        " Board:\n"
        "wR . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 150 150\n"
        "wait 1000\n"
        "print board\n",
        ["wR . .", ". . .", ". . ."],
    )


def test_grader_16_bishop_diagonal_valid():
    assert_output(
        " Board:\n"
        "wB . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 250\n"
        "wait 2000\n"
        "print board\n",
        [". . .", ". . .", ". . wB"],
    )


def test_grader_17_knight_L_valid():
    assert_output(
        " Board:\n"
        "wN . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 150 250\n"
        "wait 3000\n"
        "print board\n",
        [". . .", ". . .", ". wN ."],
    )


def test_grader_18_queen_diagonal_valid():
    assert_output(
        " Board:\n"
        "wQ . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 250\n"
        "wait 2000\n"
        "print board\n",
        [". . .", ". . .", ". . wQ"],
    )


def test_grader_19_rook_blocked_by_own_piece():
    assert_output(
        " Board:\n"
        "wR wP .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 2000\n"
        "print board\n",
        ["wR wP ."],
    )


def test_grader_20_bishop_blocked_by_own_piece():
    assert_output(
        " Board:\n"
        "wB . .\n"
        ". wP .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 250\n"
        "wait 2000\n"
        "print board\n",
        ["wB . .", ". wP .", ". . ."],
    )


def test_grader_21_knight_jumps_over_blockers():
    assert_output(
        " Board:\n"
        "wN wP .\n"
        "wP . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 150 250\n"
        "wait 3000\n"
        "print board\n",
        [". wP .", "wP . .", ". wN ."],
    )


def test_grader_26_two_cell_move_before_and_after_arrival():
    assert_output(
        " Board:\n"
        "wR . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 1000\n"
        "print board\n"
        "wait 1000\n"
        "print board\n",
        ["wR . .", ". . wR"],
    )


def test_grader_28_opposite_colors_parallel_horizontal_moves_both_complete():
    assert_output(
        " Board:\n"
        "wR . .\n"
        ". . .\n"
        "bR . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "click 50 250\n"
        "click 250 250\n"
        "wait 2000\n"
        "print board\n",
        [". . wR", ". . .", ". . bR"],
    )


def test_grader_king_capture_ends_game_and_blocks_further_moves():
    """DOCX Iteration 6 — capture on arrival, king capture game-over."""
    assert_output(
        " Board:\n"
        "wR . bK\n"
        ". . wN\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 2000\n"
        "print board\n"
        "click 250 150\n"
        "click 50 250\n"
        "wait 2000\n"
        "print board\n",
        [". . wR", ". . wN", ". . .", ". . wR", ". . wN", ". . ."],
    )


def test_grader_invalid_slide_leaves_board_unchanged_after_wait():
    """DOCX Iteration 8 — blocked slide, board unchanged after wait."""
    assert_output(
        " Board:\n"
        "wR wP .\n"
        ". . .\n"
        ". . bK\n"
        "Commands:\n"
        "click 50 50\n"
        "click 250 50\n"
        "wait 3000\n"
        "print board\n",
        ["wR wP .", ". . .", ". . bK"],
    )


def test_grader_39_white_pawn_double_from_start_valid():
    assert_output(
        " Board:\n"
        ". . .\n"
        ". . .\n"
        ". . .\n"
        ". wP .\n"
        ". . .\n"
        "Commands:\n"
        "click 150 350\n"
        "click 150 150\n"
        "wait 2000\n"
        "print board\n",
        [". . .", ". wP .", ". . .", ". . .", ". . ."],
    )


def test_grader_40_black_pawn_double_from_start_valid():
    assert_output(
        " Board:\n"
        ". . .\n"
        ". bP .\n"
        ". . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 150 150\n"
        "click 150 350\n"
        "wait 2000\n"
        "print board\n",
        [". . .", ". . .", ". . .", ". bP .", ". . ."],
    )


def test_grader_42_white_pawn_double_from_non_start_invalid():
    assert_output(
        " Board:\n"
        ". . .\n"
        ". . .\n"
        ". . .\n"
        ". wP .\n"
        "Commands:\n"
        "click 150 350\n"
        "click 150 150\n"
        "wait 2000\n"
        "print board\n",
        [". . .", ". . .", ". . .", ". wP ."],
    )
