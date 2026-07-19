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

Future extension points (not implemented yet):
- Binary board: only Board._cells internals change; callers keep using
  get_cell / move_piece / clear_cell.
- Custom games: inject PieceRules, RuleEngine, promotion_policy, game_over_piece_type,
  pawn direction maps, and Board(valid_colors=..., valid_piece_types=...).
"""

# --- Section headers in the input protocol ---
BOARD_SECTION_HEADER = "Board:"
COMMANDS_SECTION_HEADER = "Commands:"

# --- Token conventions ---
EMPTY_CELL_TOKEN = "."
TOKEN_LENGTH = 2  # e.g. "wP" = color + piece type

# --- Default rule-set for a "standard" Kong-Fu-Chess game ---
WHITE_COLOR = "w"
BLACK_COLOR = "b"
DEFAULT_VALID_COLORS = frozenset({WHITE_COLOR, BLACK_COLOR})

# Piece type letter for the pawn - used by Game to dispatch to the
# context-aware is_legal_pawn instead of the generic is_legal.
PAWN_PIECE_TYPE = "P"

# Piece type letter for the king - used by Game to detect game-over on capture.
KING_PIECE_TYPE = "K"

ROOK_PIECE_TYPE = "R"
BISHOP_PIECE_TYPE = "B"
KNIGHT_PIECE_TYPE = "N"

# Piece type letter a pawn promotes to when no explicit choice is supplied.
DEFAULT_PROMOTION_PIECE_TYPE = "Q"
QUEEN_PIECE_TYPE = DEFAULT_PROMOTION_PIECE_TYPE

DEFAULT_VALID_PIECE_TYPES = frozenset(
    {
        KING_PIECE_TYPE,
        QUEEN_PIECE_TYPE,
        ROOK_PIECE_TYPE,
        BISHOP_PIECE_TYPE,
        KNIGHT_PIECE_TYPE,
        PAWN_PIECE_TYPE,
    }
)

# Piece types excluded from promotion targets when deriving from registered shapes.
DEFAULT_NON_PROMOTABLE_PROMOTION_TYPES = frozenset({KING_PIECE_TYPE, PAWN_PIECE_TYPE})

# Default pawn direction and start row per color (injectable via PieceRules).
DEFAULT_PAWN_FORWARD_BY_COLOR = {WHITE_COLOR: -1, BLACK_COLOR: 1}
DEFAULT_PAWN_START_ROW_BY_COLOR = {WHITE_COLOR: "bottom", BLACK_COLOR: "top"}

# Default promotion targets per piece type on the last row (injectable via Game).
DEFAULT_PROMOTION_BY_PIECE_TYPE = {PAWN_PIECE_TYPE: DEFAULT_PROMOTION_PIECE_TYPE}

# --- Click protocol: pixel <-> cell geometry ---
# A single source of truth for cell size, so it's never repeated (DRY) and
# never buried as a magic number inside click-handling logic.
CELL_SIZE_PX = 100

# --- Text commands understood by the ScriptRunner---
# Kept out of business logic (SRP / no hardcoded strings) so the protocol
# vocabulary lives in one place, same spirit as the section headers above.
CLICK_COMMAND = "click"
WAIT_COMMAND = "wait"
JUMP_COMMAND = "jump"
PROMOTE_COMMAND = "promote"
PRINT_COMMAND = "print"
PRINT_BOARD_ARGUMENT = "board"

# --- Airborne jump duration (milliseconds) ---
# Injectable via Game(jump_duration_ms=...) for custom games.
DEFAULT_JUMP_DURATION_MS = 500

# --- Real-time move travel durations (milliseconds per piece type) ---
# Injectable via Game(move_durations=...) for custom games.
DEFAULT_MOVE_DURATION_MS = dict.fromkeys(DEFAULT_VALID_PIECE_TYPES, 1000)

# --- Post-move rest durations (milliseconds per piece type) ---
# After a piece finishes an accepted travel move, it must rest before it can
# be selected or moved again. Injectable via Game/GameEngine for custom games.
DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE = dict.fromkeys(DEFAULT_VALID_PIECE_TYPES, 800)

# --- Capture score values by piece type ---
PIECE_SCORE_VALUES = {
    PAWN_PIECE_TYPE: 1,
    KNIGHT_PIECE_TYPE: 3,
    BISHOP_PIECE_TYPE: 3,
    ROOK_PIECE_TYPE: 5,
    QUEEN_PIECE_TYPE: 9,
    KING_PIECE_TYPE: 0,
}

class ErrorCode:
    """String codes reported to the caller on parsing failures."""
    EMPTY_BOARD = "EMPTY_BOARD"
    ROW_WIDTH_MISMATCH = "ROW_WIDTH_MISMATCH"
    UNKNOWN_TOKEN = "UNKNOWN_TOKEN"
    MISSING_SECTION = "MISSING_SECTION"
    DUPLICATE_OCCUPANCY = "DUPLICATE_OCCUPANCY"
    DUPLICATE_PIECE_ID = "DUPLICATE_PIECE_ID"
    UNKNOWN_PIECE_ID = "UNKNOWN_PIECE_ID"
    INVALID_PROMOTION_TYPE = "INVALID_PROMOTION_TYPE"
    MISSING_PROMOTION_CHOICE = "MISSING_PROMOTION_CHOICE"
