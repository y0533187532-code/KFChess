from kongfu_chess.config import CELL_SIZE_PX

from .board_coordinates import cell_to_pixels
from ..core.img import Img


REST_COUNTDOWN_OVERLAY_COLOR = (255, 210, 0, 255)
REST_COUNTDOWN_OVERLAY_ALPHA = 0.30
LEGAL_DESTINATION_OVERLAY_COLOR = (0, 255, 0, 90)
LEGAL_DESTINATION_ALPHA = 0.35
SELECTION_BORDER_PX = 4
SELECTION_COLOR = (0, 255, 255, 255)


def draw_selection(board: Img, row: int, col: int) -> None:
    """Draw a visible selection frame on one board cell."""
    x, y = cell_to_pixels(row, col)

    board.img[y:y + SELECTION_BORDER_PX, x:x + CELL_SIZE_PX] = SELECTION_COLOR
    board.img[
        y + CELL_SIZE_PX - SELECTION_BORDER_PX:y + CELL_SIZE_PX,
        x:x + CELL_SIZE_PX,
    ] = SELECTION_COLOR
    board.img[y:y + CELL_SIZE_PX, x:x + SELECTION_BORDER_PX] = SELECTION_COLOR
    board.img[
        y:y + CELL_SIZE_PX,
        x + CELL_SIZE_PX - SELECTION_BORDER_PX:x + CELL_SIZE_PX,
    ] = SELECTION_COLOR


def draw_legal_destination(board: Img, row: int, col: int) -> None:
    """Draw a transparent green overlay on a legal destination square."""
    x, y = cell_to_pixels(row, col)

    square = board.img[
        y:y + CELL_SIZE_PX,
        x:x + CELL_SIZE_PX,
    ]

    _blend_overlay(square, LEGAL_DESTINATION_OVERLAY_COLOR, LEGAL_DESTINATION_ALPHA)


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
        overlay_y:y + CELL_SIZE_PX,
        x:x + CELL_SIZE_PX,
    ]

    _blend_overlay(overlay_area, REST_COUNTDOWN_OVERLAY_COLOR, REST_COUNTDOWN_OVERLAY_ALPHA)


def _blend_overlay(area, color: tuple[int, int, int, int], alpha: float) -> None:
    """Blend a transparent color over an image area."""
    area[:, :, 0] = (
        area[:, :, 0] * (1 - alpha) + color[0] * alpha
    ).astype(area.dtype)
    area[:, :, 1] = (
        area[:, :, 1] * (1 - alpha) + color[1] * alpha
    ).astype(area.dtype)
    area[:, :, 2] = (
        area[:, :, 2] * (1 - alpha) + color[2] * alpha
    ).astype(area.dtype)
