from kongfu_chess.client.text_display import prepare_opencv_display_text


def test_hebrew_word_is_reversed_for_opencv():
    assert prepare_opencv_display_text("התחברות", rtl=True) == "תורבחתה"


def test_latin_text_is_unchanged_in_rtl_mode():
    assert prepare_opencv_display_text("player1", rtl=True) == "player1"


def test_mixed_rating_line_orders_segments_for_rtl_display():
    rendered = prepare_opencv_display_text("דירוג: 1200", rtl=True)
    assert rendered == "1200 :גוריד"


def test_non_rtl_mode_keeps_logical_text():
    assert prepare_opencv_display_text("התחברות", rtl=False) == "התחברות"


def test_room_code_is_not_reversed_in_mixed_hebrew_line():
    rendered = prepare_opencv_display_text("קוד חדר: 5LYRT6", rtl=True)
    assert "5LYRT6" in rendered
    assert "6LYRT5" not in rendered


def test_hebrew_piece_move_keeps_chess_coordinates_readable():
    rendered = prepare_opencv_display_text("רגלי: g7->g5", rtl=True)
    assert "g7->g5" in rendered
    assert prepare_opencv_display_text("רגלי", rtl=True) in rendered
