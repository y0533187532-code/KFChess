from ..board.board_coordinates import BOARD_SIZE_PX
from ..core.img import Img


HEADER_HEIGHT_PX = 80
SIDE_PANEL_WIDTH_PX = 220
SCREEN_WIDTH_PX = BOARD_SIZE_PX + SIDE_PANEL_WIDTH_PX * 2
SCREEN_HEIGHT_PX = BOARD_SIZE_PX + HEADER_HEIGHT_PX

BOARD_X_PX = SIDE_PANEL_WIDTH_PX
BOARD_Y_PX = HEADER_HEIGHT_PX

BACKGROUND_COLOR = (30, 30, 30, 255)
PANEL_COLOR = (45, 45, 45, 255)
HEADER_COLOR = (60, 60, 60, 255)


def build_screen_canvas() -> Img:
    """Create the full UI canvas with header and side panels."""
    canvas = Img()
    canvas.blank(
        width=SCREEN_WIDTH_PX,
        height=SCREEN_HEIGHT_PX,
        color=BACKGROUND_COLOR,
    )

    canvas.img[0:HEADER_HEIGHT_PX, 0:SCREEN_WIDTH_PX] = HEADER_COLOR
    canvas.img[HEADER_HEIGHT_PX:SCREEN_HEIGHT_PX, 0:SIDE_PANEL_WIDTH_PX] = PANEL_COLOR
    canvas.img[
        HEADER_HEIGHT_PX:SCREEN_HEIGHT_PX,
        SIDE_PANEL_WIDTH_PX + BOARD_SIZE_PX:SCREEN_WIDTH_PX,
    ] = PANEL_COLOR

    return canvas


def draw_board_on_screen(screen: Img, board: Img) -> None:
    """Draw the board image in the center area of the full screen canvas."""
    board.draw_on(screen, BOARD_X_PX, BOARD_Y_PX)


def draw_status_text(screen: Img, text: str) -> None:
    """Draw a short game status line in the header area."""
    screen.put_text(
        text,
        x=20,
        y=50,
        font_size=0.8,
        color=(255, 255, 255, 255),
        thickness=2,
    )


def screen_to_board_pixels(pixel_x: int, pixel_y: int) -> tuple[int, int] | None:
    """Convert full-screen pixel coordinates into board-local coordinates."""
    board_x = pixel_x - BOARD_X_PX
    board_y = pixel_y - BOARD_Y_PX

    if board_x < 0 or board_y < 0:
        return None
    if board_x >= BOARD_SIZE_PX or board_y >= BOARD_SIZE_PX:
        return None

    return board_x, board_y


def draw_side_panel_text(screen: Img, left_lines: list[str], right_lines: list[str]) -> None:
    """Draw text lines inside the left and right side panels."""
    draw_panel_lines(
        screen,
        x=20,
        y=HEADER_HEIGHT_PX + 40,
        lines=left_lines,
    )

    draw_panel_lines(
        screen,
        x=BOARD_X_PX + BOARD_SIZE_PX + 20,
        y=HEADER_HEIGHT_PX + 40,
        lines=right_lines,
    )


def draw_panel_lines(screen: Img, x: int, y: int, lines: list[str]) -> None:
    """Draw multiple text lines starting at the requested screen position."""
    line_gap = 30

    for index, line in enumerate(lines):
        screen.put_text(
            line,
            x=x,
            y=y + index * line_gap,
            font_size=0.65,
            color=(255, 255, 255, 255),
            thickness=2,
        )
