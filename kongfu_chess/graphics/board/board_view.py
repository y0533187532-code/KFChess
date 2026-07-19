"""Board and piece rendering helpers built on top of the supplied Img class."""

from kongfu_chess.config import CELL_SIZE_PX
from kongfu_chess.engine.types import GameSnapshot
from kongfu_chess.model.piece_state import PieceState

from ..core.img import Img
from .board_assets import ASSETS_PATH, BOARD_PATH, PIECES_PATH, load_board, load_piece
from .board_coordinates import BOARD_CELLS_PER_SIDE, BOARD_SIZE_PX, cell_to_pixels
from .board_overlays import draw_legal_destination, draw_rest_timer, draw_selection
from ..pieces.piece_assets import piece_token_to_asset_name

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
        if piece.state == PieceState.CAPTURED:
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
