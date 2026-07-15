"""Board and piece rendering helpers built on top of the supplied Img class."""

from pathlib import Path
from kongfu_chess.model.piece import PIECE_STATE_CAPTURED
from kongfu_chess.config import CELL_SIZE_PX
from kongfu_chess.engine.types import GameSnapshot

from .img import Img


ASSETS_PATH = Path(__file__).resolve().parents[1] / "assets"
BOARD_PATH = ASSETS_PATH / "board.png"
PIECES_PATH = ASSETS_PATH / "pieces"

REST_TIMER_BAR_HEIGHT_PX = 14
REST_TIMER_COLOR = (255, 210, 0, 255)
REST_TIMER_BACKGROUND_COLOR = (25, 25, 25, 255)
REST_TIMER_BORDER_COLOR = (255, 255, 255, 255)
REST_TIMER_BORDER_PX = 2
REST_COUNTDOWN_OVERLAY_COLOR = (255, 210, 0, 255)
REST_COUNTDOWN_OVERLAY_ALPHA = 0.30
LEGAL_DESTINATION_OVERLAY_COLOR = (0, 255, 0, 90)
LEGAL_DESTINATION_ALPHA = 0.35
BOARD_CELLS_PER_SIDE = 8
BOARD_SIZE_PX = CELL_SIZE_PX * BOARD_CELLS_PER_SIDE
DEFAULT_PIECE_STATE = "idle"
DEFAULT_PIECE_FRAME = 1

DEMO_INITIAL_LAYOUT = [
    ["RB", "NB", "BB", "QB", "KB", "BB", "NB", "RB"],
    ["PB", "PB", "PB", "PB", "PB", "PB", "PB", "PB"],
    [None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None],
    [None, None, None, None, None, None, None, None],
    ["PW", "PW", "PW", "PW", "PW", "PW", "PW", "PW"],
    ["RW", "NW", "BW", "QW", "KW", "BW", "NW", "RW"],
]


def load_board() -> Img:
    """Load the board at a size divisible into eight equal cells."""
    return Img().read(
        BOARD_PATH,
        size=(BOARD_SIZE_PX, BOARD_SIZE_PX),
    )


def load_piece(piece_name: str, state: str, frame: int) -> Img:
    """Load one animation frame and resize it to one board cell."""
    sprite_path = (
        PIECES_PATH
        / piece_name
        / "states"
        / state
        / "sprites"
        / f"{frame}.png"
    )

    return Img().read(
        sprite_path,
        size=(CELL_SIZE_PX, CELL_SIZE_PX),
    )


def cell_to_pixels(row: int, col: int) -> tuple[int, int]:
    """Convert a board cell into its top-left pixel coordinates."""
    x = col * CELL_SIZE_PX
    y = row * CELL_SIZE_PX
    return x, y


def draw_piece(
    board: Img,
    piece_name: str,
    row: int,
    col: int,
    state: str = DEFAULT_PIECE_STATE,
    frame: int = DEFAULT_PIECE_FRAME,
) -> None:
    """Draw one piece in the requested board cell."""
    piece = load_piece(piece_name, state, frame)
    x, y = cell_to_pixels(row, col)
    piece.draw_on(board, x, y)


def piece_token_to_asset_name(token: str) -> str:
    """Convert logical tokens such as 'wK' into asset names such as 'KW'."""
    color = token[0].upper()
    piece_type = token[1].upper()
    return f"{piece_type}{color}"


def render_piece_layout(layout: list[list[str | None]]) -> Img:
    """Render a board from an explicit asset-name layout."""
    board = load_board()

    for row, board_row in enumerate(layout):
        for col, piece_name in enumerate(board_row):
            if piece_name is not None:
                draw_piece(board, piece_name, row, col)

    return board


def render_snapshot(snapshot: GameSnapshot) -> Img:
    """Render a read-only game snapshot into a board image."""
    board = load_board()

    for piece in snapshot.pieces:
        if piece.state == PIECE_STATE_CAPTURED:
            continue
        draw_piece(
            board,
            piece_token_to_asset_name(piece.token),
            piece.row,
            piece.col,
            state=piece.state,
        )

    return board


def build_demo_board() -> Img:
    """Create the standard initial chess position for a manual demo."""
    return render_piece_layout(DEMO_INITIAL_LAYOUT)


def show_board() -> None:
    build_demo_board().show()


def draw_selection(board: Img, row: int, col: int) -> None:
    """Draw a visible selection frame on one board cell."""
    x, y = cell_to_pixels(row, col)
    border = 4
    color = (0, 255, 255, 255)

    board.img[y:y + border, x:x + CELL_SIZE_PX] = color
    board.img[y + CELL_SIZE_PX - border:y + CELL_SIZE_PX, x:x + CELL_SIZE_PX] = color
    board.img[y:y + CELL_SIZE_PX, x:x + border] = color
    board.img[y:y + CELL_SIZE_PX, x + CELL_SIZE_PX - border:x + CELL_SIZE_PX] = color


def draw_legal_destination(board: Img, row: int, col: int) -> None:
    """Draw a transparent green overlay on a legal destination square."""
    x, y = cell_to_pixels(row, col)

    square = board.img[
        y : y + CELL_SIZE_PX,
        x : x + CELL_SIZE_PX,
    ]

    overlay_color = LEGAL_DESTINATION_OVERLAY_COLOR
    alpha = LEGAL_DESTINATION_ALPHA

    square[:, :, 0] = (
        square[:, :, 0] * (1 - alpha) + overlay_color[0] * alpha
    ).astype(square.dtype)
    square[:, :, 1] = (
        square[:, :, 1] * (1 - alpha) + overlay_color[1] * alpha
    ).astype(square.dtype)
    square[:, :, 2] = (
        square[:, :, 2] * (1 - alpha) + overlay_color[2] * alpha
    ).astype(square.dtype)


def draw_rest_timer(
    board: Img,
    row: int,
    col: int,
    remaining_ms: int,
    total_ms: int,
) -> None:
    """Draw a transparent countdown overlay on a resting piece's square."""
    if total_ms <= 0:
        return

    remaining_ratio = remaining_ms / total_ms
    remaining_ratio = max(0.0, min(1.0, remaining_ratio))

    x, y = cell_to_pixels(row, col)
    overlay_height = int(CELL_SIZE_PX * remaining_ratio)
    overlay_y = y + CELL_SIZE_PX - overlay_height

    overlay_area = board.img[
        overlay_y : y + CELL_SIZE_PX,
        x : x + CELL_SIZE_PX,
    ]

    overlay_color = REST_COUNTDOWN_OVERLAY_COLOR
    alpha = REST_COUNTDOWN_OVERLAY_ALPHA

    overlay_area[:, :, 0] = (
        overlay_area[:, :, 0] * (1 - alpha) + overlay_color[0] * alpha
    ).astype(overlay_area.dtype)
    overlay_area[:, :, 1] = (
        overlay_area[:, :, 1] * (1 - alpha) + overlay_color[1] * alpha
    ).astype(overlay_area.dtype)
    overlay_area[:, :, 2] = (
        overlay_area[:, :, 2] * (1 - alpha) + overlay_color[2] * alpha
    ).astype(overlay_area.dtype)


def draw_status_text(board: Img, text: str) -> None:
    """Draw a short status message near the top-left corner of the board."""
    board.put_text(
        text,
        x=10,
        y=25,
        font_size=0.7,
        color=(255, 255, 255, 255),
        thickness=2,
    )
if __name__ == "__main__":
    show_board()
