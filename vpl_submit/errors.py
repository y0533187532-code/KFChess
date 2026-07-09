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
