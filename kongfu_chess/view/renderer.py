"""View adapter stub for future GUI rendering (Iteration 9)."""

from ..engine.types import GameSnapshot


class Renderer:
    """Draws game state from a read-only snapshot. Not wired to a GUI yet."""

    def render(self, snapshot: GameSnapshot):
        raise NotImplementedError("GUI rendering is not implemented yet")
