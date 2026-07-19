from kongfu_chess.graphics.board_view import load_board
from kongfu_chess.graphics.img import Img
from kongfu_chess.graphics.screen_layout import (
    BACKGROUND_COLOR,
    BOARD_SIZE_PX,
    BOARD_X_PX,
    BOARD_Y_PX,
    HEADER_COLOR,
    HEADER_HEIGHT_PX,
    PANEL_COLOR,
    SCREEN_HEIGHT_PX,
    SCREEN_WIDTH_PX,
    SIDE_PANEL_WIDTH_PX,
    build_screen_canvas,
    draw_board_on_screen,
    draw_side_panel_text,
    draw_status_text,
    screen_to_board_pixels,
)


def test_build_screen_canvas_has_expected_size():
    screen = build_screen_canvas()

    assert isinstance(screen, Img)
    assert screen.img.shape[:2] == (SCREEN_HEIGHT_PX, SCREEN_WIDTH_PX)


def test_build_screen_canvas_draws_header_and_side_panels():
    screen = build_screen_canvas()

    assert tuple(screen.img[0, 0]) == HEADER_COLOR
    assert tuple(screen.img[HEADER_HEIGHT_PX, 0]) == BACKGROUND_COLOR
    assert tuple(screen.img[HEADER_HEIGHT_PX, SCREEN_WIDTH_PX - 1]) == BACKGROUND_COLOR
    assert tuple(screen.img[SCREEN_HEIGHT_PX - 1, SIDE_PANEL_WIDTH_PX]) == BACKGROUND_COLOR


def test_draw_board_on_screen_places_board_at_layout_offset():
    screen = build_screen_canvas()
    board = load_board()

    draw_board_on_screen(screen, board)

    assert tuple(screen.img[BOARD_Y_PX, BOARD_X_PX]) == tuple(board.img[0, 0])
    assert tuple(
        screen.img[BOARD_Y_PX + BOARD_SIZE_PX - 1, BOARD_X_PX + BOARD_SIZE_PX - 1]
    ) == tuple(board.img[BOARD_SIZE_PX - 1, BOARD_SIZE_PX - 1])


def test_draw_status_text_changes_header_pixels():
    screen = build_screen_canvas()
    before = screen.img.copy()

    draw_status_text(screen, "Ready")

    assert (before != screen.img).any()


def test_draw_side_panel_text_changes_panel_pixels():
    screen = build_screen_canvas()
    before = screen.img.copy()

    draw_side_panel_text(screen, ["White", "Pieces: 2"], ["Black", "Pieces: 1"])

    assert (before != screen.img).any()


def test_draw_side_panel_text_draws_score_labels():
    screen = build_screen_canvas()
    before = screen.img.copy()

    draw_side_panel_text(
        screen,
        ["White", "Score: 7", "Moves:"],
        ["Black", "Score: 3", "Moves:"],
    )

    assert (before != screen.img).any()


def test_screen_to_board_pixels_converts_click_inside_board():
    assert screen_to_board_pixels(BOARD_X_PX + 12, BOARD_Y_PX + 34) == (12, 34)


def test_screen_to_board_pixels_ignores_click_outside_board():
    assert screen_to_board_pixels(BOARD_X_PX - 1, BOARD_Y_PX) is None
    assert screen_to_board_pixels(BOARD_X_PX, BOARD_Y_PX - 1) is None
    assert screen_to_board_pixels(BOARD_X_PX + BOARD_SIZE_PX, BOARD_Y_PX) is None
    assert screen_to_board_pixels(BOARD_X_PX, BOARD_Y_PX + BOARD_SIZE_PX) is None
