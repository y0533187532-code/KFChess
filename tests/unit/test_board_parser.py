from kongfu_chess.io.board_parser import BoardParser


def test_parse_creates_board_from_protocol_text():
    raw = "Board:\nwK .\n. bK\nCommands:\n"
    board = BoardParser().parse(raw)
    assert board.num_rows == 2
    assert board.get_cell(0, 0).token == "wK"
    assert board.get_cell(1, 1).token == "bK"


def test_parse_rows_creates_board_from_row_tokens():
    board = BoardParser().parse_rows([["wK", "."], [".", "bK"]])
    assert board.num_rows == 2
    assert board.render_rows() == ["wK .", ". bK"]
