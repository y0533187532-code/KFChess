import cv2

from kongfu_chess.engine.types import GameSnapshot, PieceSnapshot
from kongfu_chess.game import Game
from kongfu_chess.model.board import Board

from .game_view import GameView
from .img import Img
from .screen_layout import screen_to_board_pixels


SAMPLE_BOARD_SIZE = 8
SAMPLE_PAWN_COLUMNS = (3, 4, 5, 4)
SAMPLE_PAWN_STATES = ("jump", "move", "idle", "move")
SAMPLE_STEP_FRAMES = 15
GAME_WINDOW_NAME = "Kung Fu Chess"


class MouseClickBuffer:
    """Store one pending mouse click until the game loop consumes it."""

    def __init__(self) -> None:
        self._pending_click: tuple[int, int] | None = None

    def register_click(self, pixel_x: int, pixel_y: int) -> None:
        """Remember the latest click position in window pixels."""
        self._pending_click = (pixel_x, pixel_y)

    def pop_click(self) -> tuple[int, int] | None:
        """Return and clear the pending click, if one exists."""
        click = self._pending_click
        self._pending_click = None
        return click


def on_mouse_event(event, x, y, _flags, click_buffer: MouseClickBuffer) -> None:
    """Translate OpenCV left-click events into buffered pixel positions."""
    if event == cv2.EVENT_LBUTTONDOWN:
        click_buffer.register_click(x, y)


def build_sample_snapshot(step: int = 0) -> GameSnapshot:
    """Create a simple changing snapshot for manual window testing."""
    pawn_index = step % len(SAMPLE_PAWN_COLUMNS)
    pawn_col = SAMPLE_PAWN_COLUMNS[pawn_index]
    pawn_state = SAMPLE_PAWN_STATES[pawn_index]

    return GameSnapshot(
        board_width=SAMPLE_BOARD_SIZE,
        board_height=SAMPLE_BOARD_SIZE,
        game_over=False,
        pieces=(
            PieceSnapshot(row=7, col=4, token="wK", piece_id=1, state="idle"),
            PieceSnapshot(row=0, col=4, token="bK", piece_id=2, state="idle"),
            PieceSnapshot(row=6, col=pawn_col, token="wP", piece_id=3, state=pawn_state),
        ),
    )


def show_sample_game_window() -> None:
    """Open a window and render the changing sample snapshot until Escape."""
    view = GameView()
    frame_count = 0

    try:
        while True:
            step = frame_count // SAMPLE_STEP_FRAMES
            snapshot = build_sample_snapshot(step)
            board = view.render(snapshot)
            pressed_key = board.show_frame(
                window_name=GAME_WINDOW_NAME,
                delay_ms=16,
            )
            frame_count += 1

            if pressed_key == 27:
                return
    finally:
        Img.close()


def build_sample_game() -> Game:
    """Create a real Game object with a simple initial board."""
    board = Board(
        [
            [".", ".", ".", ".", "bK", ".", ".", "."],
            [".", ".", ".", ".", ".", ".", ".", "."],
            [".", ".", ".", ".", ".", ".", ".", "."],
            [".", ".", ".", ".", ".", ".", ".", "."],
            [".", ".", ".", ".", ".", ".", ".", "."],
            [".", ".", ".", ".", ".", ".", ".", "."],
            [".", ".", ".", "wP", ".", ".", ".", "."],
            [".", ".", ".", ".", "wK", ".", ".", "."],
        ]
    )
    return Game(board)


def show_real_game_window() -> None:
    """Open a window, render a real Game, and handle mouse clicks."""
    game = build_sample_game()
    view = GameView()
    click_buffer = MouseClickBuffer()

    cv2.namedWindow(GAME_WINDOW_NAME)
    cv2.setMouseCallback(GAME_WINDOW_NAME, on_mouse_event, click_buffer)

    try:
        while True:
            pending_click = click_buffer.pop_click()
            if pending_click is not None:
                board_click = screen_to_board_pixels(*pending_click)
                if board_click is not None:
                    pixel_x, pixel_y = board_click
                    game.handle_click(pixel_x, pixel_y)

            game.handle_wait(16)
            snapshot = game.snapshot()
            board = view.render(snapshot, game.engine.active_moves)
            
            pressed_key = board.show_frame(
                window_name=GAME_WINDOW_NAME,
                delay_ms=16,
            )

            if pressed_key == 27:
                return
    finally:
        Img.close()


if __name__ == "__main__":
    show_real_game_window()
