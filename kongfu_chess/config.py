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

# Piece type letter for the pawn - used by Game to dispatch to the
# context-aware is_legal_pawn instead of the generic is_legal.
PAWN_PIECE_TYPE = "P"

# Piece type letter for the king - used by Game to detect game-over on capture.
KING_PIECE_TYPE = "K"

# Piece type letter a pawn promotes to on the last row.
QUEEN_PIECE_TYPE = "Q"

# --- Click protocol: pixel <-> cell geometry ---
# A single source of truth for cell size, so it's never repeated (DRY) and
# never buried as a magic number inside click-handling logic.
CELL_SIZE_PX = 100

# --- Text commands understood by the CommandRunner ---
# Kept out of business logic (SRP / no hardcoded strings) so the protocol
# vocabulary lives in one place, same spirit as the section headers above.
CLICK_COMMAND = "click"
WAIT_COMMAND = "wait"
PRINT_COMMAND = "print"
PRINT_BOARD_ARGUMENT = "board"

# --- Real-time move travel durations (milliseconds per piece type) ---
# Injectable via Game(move_durations=...) for custom games.
DEFAULT_MOVE_DURATION_MS = {
    "K": 1000,
    "Q": 1000,
    "R": 1000,
    "B": 1000,
    "N": 1000,
    "P": 1000,
}

class ErrorCode:
    """String codes reported to the caller on parsing failures."""
    EMPTY_BOARD = "EMPTY_BOARD"
    ROW_WIDTH_MISMATCH = "ROW_WIDTH_MISMATCH"
    UNKNOWN_TOKEN = "UNKNOWN_TOKEN"
    MISSING_SECTION = "MISSING_SECTION"
