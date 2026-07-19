from kongfu_chess.engine.types import GameSnapshot, MoveEventSnapshot, PieceSnapshot
from kongfu_chess.graphics.move_log import MoveLog


def test_lines_by_color_starts_with_player_headers():
    move_log = MoveLog()

    assert move_log.lines_by_color() == (
        ["White"],
        ["Black"],
    )


def test_record_new_moves_adds_white_move_to_left_panel():
    move_log = MoveLog()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=6, col=3, token="wP", piece_id=1, state="moving"),),
    )
    active_moves = [
        {
            "from": (6, 3),
            "to": (6, 5),
            "order": 0,
            "total_ms": 1000,
            "remaining": 1000,
        }
    ]

    move_log.record_new_moves(snapshot, active_moves, frame_index=0)

    left_lines, right_lines = move_log.lines_by_color()
    assert left_lines == ["White", "0.0s Pawn: d2->f2"]
    assert right_lines == ["Black"]


def test_record_new_moves_does_not_duplicate_existing_move():
    move_log = MoveLog()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=6, col=3, token="wP", piece_id=1, state="moving"),),
    )
    active_moves = [
        {
            "from": (6, 3),
            "to": (6, 5),
            "order": 0,
            "total_ms": 1000,
            "remaining": 1000,
        }
    ]

    move_log.record_new_moves(snapshot, active_moves, frame_index=0)
    move_log.record_new_moves(snapshot, active_moves, frame_index=1)

    left_lines, _right_lines = move_log.lines_by_color()
    assert left_lines == ["White", "0.0s Pawn: d2->f2"]


def test_record_new_moves_adds_black_move_to_right_panel():
    move_log = MoveLog()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=0, col=4, token="bK", piece_id=2, state="moving"),),
    )
    active_moves = [
        {
            "from": (0, 4),
            "to": (1, 4),
            "order": 2,
            "total_ms": 1000,
            "remaining": 1000,
        }
    ]

    move_log.record_new_moves(snapshot, active_moves, frame_index=0)

    left_lines, right_lines = move_log.lines_by_color()
    assert left_lines == ["White"]
    assert right_lines == ["Black", "0.0s King: e8->e7"]


def test_record_new_moves_uses_completed_move_actual_destination():
    move_log = MoveLog()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        completed_moves=(
            MoveEventSnapshot(
                piece_id=2,
                token="wQ",
                from_pos=(0, 3),
                requested_to=(0, 1),
                actual_to=(0, 2),
                reason="same_color_blocked",
            ),
        ),
    )

    move_log.record_new_moves(snapshot, active_moves=[], frame_index=0)

    left_lines, right_lines = move_log.lines_by_color()
    assert left_lines == ["White", "0.0s Queen: d8->c8 (blocked)"]
    assert right_lines == ["Black"]


def test_record_new_moves_marks_completed_capture():
    move_log = MoveLog()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        completed_moves=(
            MoveEventSnapshot(
                piece_id=2,
                token="bB",
                from_pos=(1, 1),
                requested_to=(0, 0),
                actual_to=(0, 0),
                reason="capture",
            ),
        ),
    )

    move_log.record_new_moves(snapshot, active_moves=[], frame_index=0)

    left_lines, right_lines = move_log.lines_by_color()
    assert left_lines == ["White"]
    assert right_lines == ["Black", "0.0s Bishop: b7->a8 (capture)"]


def test_record_new_moves_marks_completed_jump():
    move_log = MoveLog()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        completed_moves=(
            MoveEventSnapshot(
                piece_id=3,
                token="wN",
                from_pos=(7, 1),
                requested_to=(7, 1),
                actual_to=(7, 1),
                reason="jump",
            ),
        ),
    )

    move_log.record_new_moves(snapshot, active_moves=[], frame_index=0)

    left_lines, right_lines = move_log.lines_by_color()
    assert left_lines == ["White", "0.0s Knight: jump b1"]
    assert right_lines == ["Black"]


def test_cell_name_converts_board_position_to_chess_name():
    move_log = MoveLog()

    assert move_log._cell_name(7, 4) == "e1"
    assert move_log._cell_name(0, 0) == "a8"


def test_piece_name_converts_piece_token_to_readable_name():
    move_log = MoveLog()

    assert move_log._piece_name("wP") == "Pawn"
    assert move_log._piece_name("bK") == "King"


def test_move_log_is_trimmed_to_latest_entries():
    move_log = MoveLog()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=6, col=3, token="wP", piece_id=1, state="moving"),),
    )

    for order in range(12):
        active_moves = [
            {
                "from": (6, 3),
                "to": (6, 4),
                "order": order,
                "total_ms": 1000,
                "remaining": 1000,
            }
        ]
        move_log.record_new_moves(snapshot, active_moves, frame_index=order)

    left_lines, _right_lines = move_log.lines_by_color()
    assert len(left_lines) == 9
    assert left_lines[0] == "White"
    assert left_lines[-1].endswith("Pawn: d2->e2")
