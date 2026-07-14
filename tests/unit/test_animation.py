from kongfu_chess.graphics.animation import Animation
from kongfu_chess.graphics.board_view import CELL_SIZE_PX
from kongfu_chess.graphics.img import Img


def test_animation_loads_config_and_frames():
    animation = Animation("KW", "idle")

    assert animation.piece_name == "KW"
    assert animation.state_name == "idle"
    assert animation.frames_per_sec > 0
    assert isinstance(animation.is_loop, bool)
    assert animation.next_state == "idle"
    assert len(animation.frames) == 5
    assert all(isinstance(frame, Img) for frame in animation.frames)
    assert all(frame.img.shape[:2] == (CELL_SIZE_PX, CELL_SIZE_PX) for frame in animation.frames)


def test_animation_reset_overrides_start_time():
    animation = Animation("KW", "idle")

    animation.reset(123.5)

    assert animation.started_at == 123.5


def test_looping_animation_advances_frames_and_wraps():
    animation = Animation("KW", "idle")
    fps = animation.frames_per_sec
    animation.reset(10.0)

    first_frame = animation.frame_at(10.0)
    second_frame = animation.frame_at(10.0 + (1 / fps))
    wrapped_frame = animation.frame_at(10.0 + (len(animation.frames) / fps))

    assert first_frame is animation.frames[0]
    assert second_frame is animation.frames[1]
    assert wrapped_frame is animation.frames[0]


def test_non_looping_animation_stops_on_last_frame_and_finishes():
    animation = Animation("KW", "jump")
    fps = animation.frames_per_sec
    animation.reset(20.0)
    duration = len(animation.frames) / fps

    before_end = animation.frame_at(20.0 + (1 / fps))
    after_end = animation.frame_at(20.0 + duration + 0.01)

    assert before_end is animation.frames[1]
    assert after_end is animation.frames[-1]
    assert animation.is_finished(20.0 + duration + 0.01) is True


def test_looping_animation_is_never_finished():
    animation = Animation("KW", "idle")
    animation.reset(30.0)

    assert animation.is_finished(999.0) is False
