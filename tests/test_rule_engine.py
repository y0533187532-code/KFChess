from kongfu_chess.model.board import Board
from kongfu_chess.model.piece import Piece
from kongfu_chess.model.position import Position
from kongfu_chess.rules import PieceRules, RuleEngine


def test_validate_move_ok_for_legal_rook_move():
    board = Board([["wR", ".", "."]])
    engine = RuleEngine()
    result = engine.validate_move(board, 0, 0, 0, 2)
    assert result.is_valid is True
    assert result.reason == "ok"


def test_validate_move_outside_board():
    board = Board([["wR"]])
    engine = RuleEngine()
    result = engine.validate_move(board, 0, 0, 2, 0)
    assert result.is_valid is False
    assert result.reason == "outside_board"


def test_validate_move_empty_source():
    board = Board([[".", "wR"]])
    engine = RuleEngine()
    result = engine.validate_move(board, 0, 0, 0, 1)
    assert result.is_valid is False
    assert result.reason == "empty_source"


def test_validate_move_friendly_destination():
    board = Board([["wR", "wQ"]])
    engine = RuleEngine()
    result = engine.validate_move(board, 0, 0, 0, 1)
    assert result.is_valid is False
    assert result.reason == "friendly_destination"


def test_validate_move_illegal_piece_move():
    rows = [["wR", ".", "."], [".", ".", "."], [".", ".", "."]]
    board = Board(rows)
    engine = RuleEngine()
    result = engine.validate_move(board, 0, 0, 2, 2)
    assert result.is_valid is False
    assert result.reason == "illegal_piece_move"


def test_validate_move_blocked_sliding_path():
    board = Board([["wR", "bN", "."]])
    engine = RuleEngine()
    result = engine.validate_move(board, 0, 0, 0, 2)
    assert result.is_valid is False
    assert result.reason == "illegal_piece_move"


def test_legal_destinations_for_rook_on_open_rank():
    board = Board([["wR", ".", "."]])
    rules = PieceRules()
    piece = board.get_cell(0, 0)
    destinations = rules.legal_destinations(board, piece, 0, 0)
    assert destinations == {Position(0, 1), Position(0, 2)}


def test_legal_destinations_exclude_friendly_square():
    board = Board([["wR", "wQ", "."]])
    rules = PieceRules()
    piece = board.get_cell(0, 0)
    destinations = rules.legal_destinations(board, piece, 0, 0)
    assert Position(0, 1) not in destinations


def test_legal_destinations_include_enemy_capture_square():
    board = Board([["wR", "bQ"]])
    rules = PieceRules()
    piece = board.get_cell(0, 0)
    destinations = rules.legal_destinations(board, piece, 0, 0)
    assert Position(0, 1) in destinations
