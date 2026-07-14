from kongfu_chess.engine.types import GameSnapshot, PieceSnapshot
from kongfu_chess.graphics.game_view import GameView
from kongfu_chess.graphics.img import Img
from kongfu_chess.graphics.piece_animator import PieceAnimator


def test_render_returns_img_board():
    view = GameView()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=7, col=4, token="wK", piece_id=1),),
    )

    board = view.render(snapshot)

    assert isinstance(board, Img)
    assert board.img is not None


def test_render_creates_animator_per_piece_id():
    view = GameView()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=7, col=4, token="wK", piece_id=11),),
    )

    view.render(snapshot)

    assert 11 in view._animators_by_piece_id
    assert isinstance(view._animators_by_piece_id[11], PieceAnimator)


def test_render_reuses_existing_animator_when_piece_is_unchanged():
    view = GameView()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=7, col=4, token="wK", piece_id=5),),
    )

    view.render(snapshot)
    first_animator = view._animators_by_piece_id[5]
    view.render(snapshot)
    second_animator = view._animators_by_piece_id[5]

    assert first_animator is second_animator


def test_render_updates_animator_state_when_state_changes():
    view = GameView()
    idle_snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=7, col=4, token="wK", piece_id=3, state="idle"),),
    )
    jump_snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=7, col=4, token="wK", piece_id=3, state="jump"),),
    )

    view.render(idle_snapshot)
    view.render(jump_snapshot)

    assert view._animators_by_piece_id[3].state_name == "jump"


def test_render_replaces_animator_when_piece_type_changes():
    view = GameView()
    first_snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=7, col=4, token="wK", piece_id=9),),
    )
    second_snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=7, col=4, token="wQ", piece_id=9),),
    )

    view.render(first_snapshot)
    first_animator = view._animators_by_piece_id[9]
    view.render(second_snapshot)
    second_animator = view._animators_by_piece_id[9]

    assert first_animator is not second_animator
    assert second_animator.piece_name == "QW"


def test_render_maps_moving_state_to_move_assets():
    view = GameView()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=6, col=3, token="wP", piece_id=4, state="moving"),),
    )

    view.render(snapshot)

    assert view._animators_by_piece_id[4].state_name == "move"


def test_unknown_state_falls_back_to_idle_assets():
    view = GameView()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=6, col=3, token="wP", piece_id=8, state="something_else"),),
    )

    view.render(snapshot)

    assert view._animators_by_piece_id[8].state_name == "idle"
