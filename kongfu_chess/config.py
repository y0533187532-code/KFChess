"""Configuration for board / piece parsing.

Every "magic" literal used by the parsing and validation logic lives here,
not inline in business logic. This has two purposes:

1. DRY / no-hardcoded-constants: a single source of truth for section
   headers, the empty-cell token, and error codes.
2. Extensibility for future "design your own game" support: the piece
   types and colors below are only the *default* rule-set for a standard
   Kong-Fu-Chess game. Nothing in board.py / piece.py assumes these exact
   values - they are passed in as parameters with these as defaults, so a
   custom game can supply a completely different rule-set (different piece
   letters, more than two colors, etc.) without touching any parsing code.
"""

# --- Section headers in the input protocol ---
BOARD_SECTION_HEADER = "Board:"
COMMANDS_SECTION_HEADER = "Commands:"

# --- Token conventions ---
EMPTY_CELL_TOKEN = "."
TOKEN_LENGTH = 2  # e.g. "wP" = color + piece type

# --- Default rule-set for a "standard" Kong-Fu-Chess game ---
DEFAULT_VALID_PIECE_TYPES = frozenset({"K", "Q", "R", "B", "N", "P"})
DEFAULT_VALID_COLORS = frozenset({"w", "b"})


class ErrorCode:
    """String codes reported to the caller on parsing failures."""
    EMPTY_BOARD = "EMPTY_BOARD"
    ROW_WIDTH_MISMATCH = "ROW_WIDTH_MISMATCH"
    UNKNOWN_TOKEN = "UNKNOWN_TOKEN"
    MISSING_SECTION = "MISSING_SECTION"
