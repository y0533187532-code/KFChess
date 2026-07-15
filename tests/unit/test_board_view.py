from kongfu_chess.graphics.board_view import (
    BOARD_PATH,
    BOARD_SIZE_PX,
    CELL_SIZE_PX,
    DEMO_INITIAL_LAYOUT,
    build_demo_board,
    cell_to_pixels,
    draw_legal_destination,
    draw_rest_timer,
    draw_selection,
    draw_piece,
    load_board,
    load_piece,
    piece_token_to_asset_name,
    render_piece_layout,
    render_snapshot,
)
from kongfu_chess.graphics.img import Img
from kongfu_chess.engine.types import GameSnapshot, PieceSnapshot
from kongfu_chess.model.piece import PIECE_STATE_CAPTURED


def test_board_asset_exists():
    assert BOARD_PATH.is_file()


def test_load_board_uses_img():
    board = load_board()

    assert isinstance(board, Img)
    assert board.img is not None
    assert board.img.shape[:2] == (BOARD_SIZE_PX, BOARD_SIZE_PX)


def test_load_piece_returns_resized_img():
    piece = load_piece("KW", "idle", 1)

    assert isinstance(piece, Img)
    assert piece.img is not None
    assert piece.img.shape[:2] == (CELL_SIZE_PX, CELL_SIZE_PX)


def test_cell_to_pixels_maps_grid_to_top_left_corner():
    assert cell_to_pixels(0, 0) == (0, 0)
    assert cell_to_pixels(7, 4) == (4 * CELL_SIZE_PX, 7 * CELL_SIZE_PX)


def test_draw_piece_changes_board_pixels():
    board = load_board()
    before = board.img.copy()

    draw_piece(board, "KW", 7, 4)

    assert (before != board.img).any()


def test_build_demo_board_contains_pieces():
    board = build_demo_board()

    assert isinstance(board, Img)
    assert board.img is not None


def test_piece_token_to_asset_name_maps_logical_token_to_asset_name():
    assert piece_token_to_asset_name("wK") == "KW"
    assert piece_token_to_asset_name("bQ") == "QB"


def test_render_piece_layout_draws_given_asset_layout():
    board = render_piece_layout([[None, None], [None, "KW"]])

    assert isinstance(board, Img)
    assert board.img is not None


def test_build_demo_board_uses_demo_layout():
    board = build_demo_board()
    expected = render_piece_layout(DEMO_INITIAL_LAYOUT)

    assert (board.img == expected.img).all()


def test_render_snapshot_draws_piece_from_snapshot_token():
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(PieceSnapshot(row=7, col=4, token="wK", piece_id=1),),
    )

    board = render_snapshot(snapshot)

    assert isinstance(board, Img)
    assert board.img is not None


def test_render_snapshot_skips_captured_pieces():
    empty_board = load_board()
    snapshot = GameSnapshot(
        board_width=8,
        board_height=8,
        game_over=False,
        pieces=(
            PieceSnapshot(
                row=7,
                col=4,
                token="wK",
                piece_id=1,
                state=PIECE_STATE_CAPTURED,
            ),
        ),
    )

    board = render_snapshot(snapshot)

    assert (board.img == empty_board.img).all()


def test_draw_selection_changes_board_border_pixels():
    board = load_board()
    x, y = cell_to_pixels(7, 4)
    before = board.img.copy()

    draw_selection(board, 7, 4)

    assert (before[y, x] != board.img[y, x]).any()
    assert (before[y + CELL_SIZE_PX - 1, x + CELL_SIZE_PX - 1] != board.img[y + CELL_SIZE_PX - 1, x + CELL_SIZE_PX - 1]).any()


def test_draw_rest_timer_draws_partial_countdown_overlay():
    board = load_board()
    x, y = cell_to_pixels(6, 3)
    top_pixel_before = board.img[y, x].copy()
    lower_pixel_before = board.img[y + CELL_SIZE_PX - 1, x].copy()

    draw_rest_timer(board, 6, 3, remaining_ms=1000, total_ms=2000)

    assert (board.img[y, x] == top_pixel_before).all()
    assert (board.img[y + CELL_SIZE_PX - 1, x] != lower_pixel_before).any()
    assert board.img[y + CELL_SIZE_PX - 1, x][2] < lower_pixel_before[2]


def test_draw_legal_destination_adds_green_overlay_to_square():
    board = load_board()
    x, y = cell_to_pixels(6, 3)
    before = board.img[y, x].copy()

    draw_legal_destination(board, 6, 3)

    after = board.img[y, x]
    assert after[1] > before[1]
