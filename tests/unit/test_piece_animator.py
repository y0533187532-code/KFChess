from kongfu_chess.graphics.piece_animator import PieceAnimator


def test_piece_animator_starts_in_requested_state():
    animator = PieceAnimator("KW", "idle", now=100.0)

    assert animator.piece_name == "KW"
    assert animator.state_name == "idle"
    assert animator.animation.started_at == 100.0


def test_piece_animator_change_state_replaces_animation():
    animator = PieceAnimator("KW", "idle", now=100.0)
    previous_animation = animator.animation

    animator.change_state("jump", now=150.0)

    assert animator.state_name == "jump"
    assert animator.animation is not previous_animation
    assert animator.animation.started_at == 150.0


def test_piece_animator_keeps_current_state_while_animation_is_running():
    animator = PieceAnimator("KW", "jump", now=200.0)

    animator.update(200.01)

    assert animator.state_name == "jump"


def test_piece_animator_moves_to_next_state_when_finished():
    animator = PieceAnimator("KW", "jump", now=300.0)
    duration = len(animator.animation.frames) / animator.animation.frames_per_sec

    animator.update(300.0 + duration + 0.01)

    assert animator.state_name == "short_rest"


def test_piece_animator_frame_at_can_chain_state_transitions():
    animator = PieceAnimator("KW", "jump", now=400.0)
    jump_duration = len(animator.animation.frames) / animator.animation.frames_per_sec

    frame_after_jump = animator.frame_at(400.0 + jump_duration + 0.01)

    assert animator.state_name == "short_rest"
    assert frame_after_jump is animator.animation.frames[0]

    short_rest_duration = len(animator.animation.frames) / animator.animation.frames_per_sec
    frame_after_rest = animator.frame_at(400.0 + jump_duration + short_rest_duration + 0.02)

    assert animator.state_name == "idle"
    assert frame_after_rest is animator.animation.frames[0]
