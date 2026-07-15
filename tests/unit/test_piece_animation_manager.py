from kongfu_chess.graphics.img import Img
from kongfu_chess.graphics.piece_animation_manager import PieceAnimationManager
from kongfu_chess.graphics.piece_animator import PieceAnimator


def test_animator_for_creates_animator_per_piece_id():
    manager = PieceAnimationManager()

    animator = manager.animator_for(11, "wK", "idle")

    assert 11 in manager.animators_by_piece_id
    assert manager.animators_by_piece_id[11] is animator
    assert isinstance(animator, PieceAnimator)


def test_animator_for_reuses_existing_animator_when_piece_is_unchanged():
    manager = PieceAnimationManager()

    first_animator = manager.animator_for(5, "wK", "idle")
    second_animator = manager.animator_for(5, "wK", "idle")

    assert first_animator is second_animator


def test_animator_for_updates_state_when_state_changes():
    manager = PieceAnimationManager()

    manager.animator_for(3, "wK", "idle")
    animator = manager.animator_for(3, "wK", "jump")

    assert animator.state_name == "jump"


def test_animator_for_replaces_animator_when_piece_type_changes():
    manager = PieceAnimationManager()

    first_animator = manager.animator_for(9, "wK", "idle")
    second_animator = manager.animator_for(9, "wQ", "idle")

    assert first_animator is not second_animator
    assert second_animator.piece_name == "QW"


def test_frame_for_returns_current_animation_frame():
    manager = PieceAnimationManager()

    frame = manager.frame_for(1, "wK", "idle")

    assert isinstance(frame, Img)
