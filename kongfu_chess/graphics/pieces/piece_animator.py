from ..animation import Animation
from ..core.img import Img


class PieceAnimator:
    """Manage the current animation state of one chess piece."""

    def __init__(
        self,
        piece_name: str,
        initial_state: str = "idle",
        now: float | None = None,
    ):
        self.piece_name = piece_name
        self.state_name = initial_state
        self.animation = Animation(piece_name, initial_state)
        self.animation.reset(now)

    def change_state(
        self,
        new_state: str,
        now: float | None = None,
    ) -> None:
        """Move the piece to a new animation state."""
        self.state_name = new_state
        self.animation = Animation(self.piece_name, new_state)
        self.animation.reset(now)

    def update(self, now: float | None = None) -> None:
        """Move to the configured next state when animation finishes."""
        if self.animation.is_finished(now):
            next_state = self.animation.next_state
            self.change_state(next_state, now)

    def frame_at(self, now: float | None = None) -> Img:
        """Update the state and return its current image."""
        self.update(now)
        return self.animation.frame_at(now)
