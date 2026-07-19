"""Exceptions raised while parsing the board / input protocol.

Using exceptions instead of print() + sys.exit() keeps parsing logic pure
and testable: a unit test can simply assert a specific exception (and its
.code) was raised, with no need to capture stdout or patch sys.exit/stdin.
"""

try:
    from .config import ErrorCode
except ImportError:
    from config import ErrorCode


class BoardParsingError(Exception):
    """Base class for every parsing error in this package."""

    code = None

    def __init__(self, message=""):
        super().__init__(message or self.code)


class EmptyBoardError(BoardParsingError):
    code = ErrorCode.EMPTY_BOARD

    def __init__(self):
        super().__init__("The board section contains no rows")


class RowWidthMismatchError(BoardParsingError):
    code = ErrorCode.ROW_WIDTH_MISMATCH

    def __init__(self):
        super().__init__("Not all board rows have the same width")


class UnknownTokenError(BoardParsingError):
    code = ErrorCode.UNKNOWN_TOKEN

    def __init__(self, token):
        self.token = token
        super().__init__(f"Unknown board token: {token!r}")


class MissingSectionError(BoardParsingError):
    code = ErrorCode.MISSING_SECTION

    def __init__(self, header):
        self.header = header
        super().__init__(f"Missing required section header: {header!r}")


class DuplicateOccupancyError(BoardParsingError):
    code = ErrorCode.DUPLICATE_OCCUPANCY

    def __init__(self, row, col):
        self.row = row
        self.col = col
        super().__init__(f"Cell ({row}, {col}) is already occupied")


class DuplicatePieceIdError(BoardParsingError):
    code = ErrorCode.DUPLICATE_PIECE_ID

    def __init__(self, piece_id):
        self.piece_id = piece_id
        super().__init__(f"Duplicate piece id: {piece_id}")


class UnknownPieceIdError(BoardParsingError):
    code = ErrorCode.UNKNOWN_PIECE_ID

    def __init__(self, piece_id):
        self.piece_id = piece_id
        super().__init__(f"Unknown piece id: {piece_id}")


class InvalidPromotionTypeError(Exception):
    code = ErrorCode.INVALID_PROMOTION_TYPE

    def __init__(self, piece_type):
        self.piece_type = piece_type
        super().__init__(f"Invalid promotion piece type: {piece_type!r}")


class MissingPromotionChoiceError(Exception):
    code = ErrorCode.MISSING_PROMOTION_CHOICE

    def __init__(self):
        super().__init__("Promotion choice required when queen is not allowed")
