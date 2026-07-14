import json
import time

from .board_view import CELL_SIZE_PX, PIECES_PATH
from .img import Img


class Animation:
    """Manage the graphics of one piece state."""

    def __init__(self, piece_name: str, state_name: str):
        self.piece_name = piece_name
        self.state_name = state_name

        state_path = (
            PIECES_PATH
            / piece_name
            / "states"
            / state_name
        )

        config_path = state_path / "config.json"
        sprites_path = state_path / "sprites"

        with config_path.open(encoding="utf-8") as config_file:
            config = json.load(config_file)

        graphics = config["graphics"]
        physics = config["physics"]

        self.frames_per_sec = graphics["frames_per_sec"]
        self.is_loop = graphics["is_loop"]
        self.speed_m_per_sec = physics["speed_m_per_sec"]
        self.next_state = physics["next_state_when_finished"]

        sprite_paths = sorted(
            sprites_path.glob("*.png"),
            key=lambda path: int(path.stem),
        )

        self.frames = [
            Img().read(
                sprite_path,
                size=(CELL_SIZE_PX, CELL_SIZE_PX),
            )
            for sprite_path in sprite_paths
        ]

        self.started_at = time.monotonic()

    def reset(self, now: float | None = None) -> None:
        """Restart the animation from its first frame."""
        self.started_at = time.monotonic() if now is None else now

    def frame_at(self, now: float | None = None) -> Img:
        """Return the frame that should be displayed at the given time."""
        current_time = time.monotonic() if now is None else now
        elapsed = current_time - self.started_at

        frame_number = int(elapsed * self.frames_per_sec + 1e-9)

        if self.is_loop:
            frame_index = frame_number % len(self.frames)
        else:
            frame_index = min(frame_number, len(self.frames) - 1)

        return self.frames[frame_index]
    
    def is_finished(self, now: float | None = None) -> bool:
        """Return whether a non-looping animation has finished."""
        if self.is_loop:
            return False

        current_time = time.monotonic() if now is None else now
        elapsed = current_time - self.started_at
        duration = len(self.frames) / self.frames_per_sec

        return elapsed >= duration