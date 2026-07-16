from ..board.board_coordinates import BOARD_SIZE_PX
from ..core.img import Img


HEADER_HEIGHT_PX = 95
FOOTER_HEIGHT_PX = 70
SIDE_PANEL_WIDTH_PX = 250
BOARD_LABEL_MARGIN_PX = 45
SCREEN_WIDTH_PX = BOARD_SIZE_PX + SIDE_PANEL_WIDTH_PX * 2 + BOARD_LABEL_MARGIN_PX * 2
SCREEN_HEIGHT_PX = BOARD_SIZE_PX + HEADER_HEIGHT_PX + FOOTER_HEIGHT_PX

BOARD_X_PX = SIDE_PANEL_WIDTH_PX + BOARD_LABEL_MARGIN_PX
BOARD_Y_PX = HEADER_HEIGHT_PX

BACKGROUND_COLOR = (135, 132, 128, 255)
PANEL_COLOR = (246, 246, 246, 255)
HEADER_COLOR = BACKGROUND_COLOR
TABLE_BORDER_COLOR = (210, 210, 210, 255)
TABLE_HEADER_COLOR = (255, 255, 255, 255)
TEXT_COLOR = (25, 25, 25, 255)
BOARD_LABEL_COLOR = (15, 15, 15, 255)
TABLE_ROW_HEIGHT_PX = 27
TABLE_TITLE_HEIGHT_PX = 40
TABLE_COLUMN_HEADER_HEIGHT_PX = 32
TABLE_X_PADDING_PX = 25


def build_screen_canvas() -> Img:
    """Create the full UI canvas with header and side panels."""
    canvas = Img()
    canvas.blank(
        width=SCREEN_WIDTH_PX,
        height=SCREEN_HEIGHT_PX,
        color=BACKGROUND_COLOR,
    )

    return canvas


def draw_board_on_screen(screen: Img, board: Img) -> None:
    """Draw the board image in the center area of the full screen canvas."""
    draw_board_coordinates(screen)
    board.draw_on(screen, BOARD_X_PX, BOARD_Y_PX)


def draw_status_text(screen: Img, text: str) -> None:
    """Draw a short game status line in the header area."""
    screen.put_text(
        text,
        x=BOARD_X_PX,
        y=45,
        font_size=0.75,
        color=TEXT_COLOR,
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
    draw_move_table(
        screen,
        x=TABLE_X_PADDING_PX,
        y=HEADER_HEIGHT_PX - 35,
        lines=left_lines,
    )

    draw_move_table(
        screen,
        x=BOARD_X_PX + BOARD_SIZE_PX + BOARD_LABEL_MARGIN_PX + TABLE_X_PADDING_PX,
        y=HEADER_HEIGHT_PX - 35,
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
            color=TEXT_COLOR,
            thickness=2,
        )


def draw_board_coordinates(screen: Img) -> None:
    """Draw chess file/rank labels around the board."""
    files = "abcdefgh"

    for index, file_letter in enumerate(files):
        x = BOARD_X_PX + index * (BOARD_SIZE_PX // 8) + 35
        screen.put_text(
            file_letter,
            x=x,
            y=BOARD_Y_PX - 15,
            font_size=0.9,
            color=BOARD_LABEL_COLOR,
            thickness=2,
        )
        screen.put_text(
            file_letter,
            x=x,
            y=BOARD_Y_PX + BOARD_SIZE_PX + 35,
            font_size=0.9,
            color=BOARD_LABEL_COLOR,
            thickness=2,
        )

    for row in range(8):
        rank = str(8 - row)
        y = BOARD_Y_PX + row * (BOARD_SIZE_PX // 8) + 62
        screen.put_text(
            rank,
            x=BOARD_X_PX - 30,
            y=y,
            font_size=0.9,
            color=BOARD_LABEL_COLOR,
            thickness=2,
        )
        screen.put_text(
            rank,
            x=BOARD_X_PX + BOARD_SIZE_PX + 12,
            y=y,
            font_size=0.9,
            color=BOARD_LABEL_COLOR,
            thickness=2,
        )


def draw_move_table(screen: Img, x: int, y: int, lines: list[str]) -> None:
    """Draw a player move table with Time and Move columns."""
    table_width = SIDE_PANEL_WIDTH_PX - TABLE_X_PADDING_PX * 2
    time_col_width = 105
    title = lines[0] if lines else ""
    moves = _move_lines_from_panel(lines)
    table_height = (
        TABLE_TITLE_HEIGHT_PX
        + TABLE_COLUMN_HEADER_HEIGHT_PX
        + max(12, len(moves)) * TABLE_ROW_HEIGHT_PX
    )

    _fill_rect(screen, x, y, table_width, table_height, PANEL_COLOR)
    _fill_rect(screen, x, y, table_width, TABLE_TITLE_HEIGHT_PX, TABLE_HEADER_COLOR)
    _fill_rect(
        screen,
        x,
        y + TABLE_TITLE_HEIGHT_PX,
        table_width,
        TABLE_COLUMN_HEADER_HEIGHT_PX,
        TABLE_HEADER_COLOR,
    )
    _draw_table_grid(screen, x, y, table_width, table_height, time_col_width)

    screen.put_text(title, x=x + table_width // 2 - 35, y=y + 27, font_size=0.55, color=TEXT_COLOR, thickness=2)
    header_y = y + TABLE_TITLE_HEIGHT_PX + 22
    screen.put_text("Time", x=x + 25, y=header_y, font_size=0.55, color=TEXT_COLOR, thickness=2)
    screen.put_text("Move", x=x + time_col_width + 30, y=header_y, font_size=0.55, color=TEXT_COLOR, thickness=2)

    row_y = y + TABLE_TITLE_HEIGHT_PX + TABLE_COLUMN_HEADER_HEIGHT_PX + 20
    for index, move_line in enumerate(moves[:14]):
        time_text, move_text = _split_move_line(move_line)
        screen.put_text(time_text, x=x + 8, y=row_y + index * TABLE_ROW_HEIGHT_PX, font_size=0.5, color=(90, 90, 90, 255), thickness=1)
        screen.put_text(move_text, x=x + time_col_width + 10, y=row_y + index * TABLE_ROW_HEIGHT_PX, font_size=0.5, color=(90, 90, 90, 255), thickness=1)


def _move_lines_from_panel(lines: list[str]) -> list[str]:
    return [line for line in lines[1:] if line != "Moves:" and not line.startswith("Score:")]


def _split_move_line(line: str) -> tuple[str, str]:
    if " " not in line:
        return "", line
    time_text, rest = line.split(" ", 1)
    if ": " in rest:
        _piece_name, move_text = rest.split(": ", 1)
        return time_text, move_text
    return time_text, rest


def _fill_rect(screen: Img, x: int, y: int, width: int, height: int, color) -> None:
    screen.img[y:y + height, x:x + width] = color


def _draw_table_grid(
    screen: Img,
    x: int,
    y: int,
    width: int,
    height: int,
    time_col_width: int,
) -> None:
    border = 1
    screen.img[y:y + border, x:x + width] = TABLE_BORDER_COLOR
    screen.img[y + height - border:y + height, x:x + width] = TABLE_BORDER_COLOR
    screen.img[y:y + height, x:x + border] = TABLE_BORDER_COLOR
    screen.img[y:y + height, x + width - border:x + width] = TABLE_BORDER_COLOR
    screen.img[y + TABLE_TITLE_HEIGHT_PX:y + TABLE_TITLE_HEIGHT_PX + border, x:x + width] = TABLE_BORDER_COLOR
    header_bottom = y + TABLE_TITLE_HEIGHT_PX + TABLE_COLUMN_HEADER_HEIGHT_PX
    screen.img[header_bottom:header_bottom + border, x:x + width] = TABLE_BORDER_COLOR
    screen.img[y + TABLE_TITLE_HEIGHT_PX:y + height, x + time_col_width:x + time_col_width + border] = TABLE_BORDER_COLOR

    first_row_y = y + TABLE_TITLE_HEIGHT_PX + TABLE_COLUMN_HEADER_HEIGHT_PX
    for row_y in range(first_row_y, y + height, TABLE_ROW_HEIGHT_PX):
        screen.img[row_y:row_y + border, x:x + width] = TABLE_BORDER_COLOR
