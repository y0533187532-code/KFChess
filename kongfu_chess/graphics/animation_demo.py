from .animation import Animation
from .board.board_coordinates import cell_to_pixels
from .board.board_assets import load_board
from .core.img import Img

def show_idle_animation() -> None:
    """Display the white king's idle animation until Escape is pressed."""
    animation = Animation("KW", "idle")
    x, y = cell_to_pixels(row=7, col=4)

    try:
        while True:
            board = load_board()
            current_frame = animation.frame_at()

            current_frame.draw_on(board, x, y)

            pressed_key = board.show_frame(delay_ms=16)
            if pressed_key == 27:
                return
    finally:
        Img.close()



if __name__ == "__main__":
    show_idle_animation()
