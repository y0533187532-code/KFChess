from pathlib import Path

from kongfu_chess.config import CELL_SIZE_PX

from .board_coordinates import BOARD_SIZE_PX
from ..core.img import Img


ASSETS_PATH = Path(__file__).resolve().parents[2] / "assets"
BOARD_PATH = ASSETS_PATH / "board.png"
PIECES_PATH = ASSETS_PATH / "pieces"


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
