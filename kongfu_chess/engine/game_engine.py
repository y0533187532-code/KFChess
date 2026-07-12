"""Application-service command boundary for move requests."""

try:
    from ..config import DEFAULT_JUMP_DURATION_MS, DEFAULT_MOVE_DURATION_MS
    from ..engine.types import GameSnapshot, MoveResult
    from ..rules import RuleEngine, get_move_route, is_route_conflict
except ImportError:
    from config import DEFAULT_JUMP_DURATION_MS, DEFAULT_MOVE_DURATION_MS
    from engine.types import GameSnapshot, MoveResult
    from rules import RuleEngine, get_move_route, is_route_conflict


class GameEngine:
    """Coordinates validation and motion scheduling; does not apply board updates on arrival."""

    def __init__(
        self,
        board,
        state,
        rule_engine=None,
        move_durations=None,
        jump_duration_ms=None,
    ):
        self._board = board
        self._state = state
        self._rule_engine = rule_engine or RuleEngine()
        self._move_durations = dict(
            move_durations if move_durations is not None else DEFAULT_MOVE_DURATION_MS
        )
        self._jump_duration_ms = (
            jump_duration_ms
            if jump_duration_ms is not None
            else DEFAULT_JUMP_DURATION_MS
        )
        self._active_moves = []
        self._next_order = 0

    @property
    def board(self):
        return self._board

    @property
    def state(self):
        return self._state

    @property
    def rule_engine(self):
        return self._rule_engine

    @property
    def active_moves(self):
        return self._active_moves

    def moving_origins(self):
        return {move["from"] for move in self._active_moves}

    def request_move(self, from_row, from_col, to_row, to_col):
        """Validate and schedule a move; board updates happen on arrival (Phase 5+)."""
        if self._state.is_game_over:
            return MoveResult(is_accepted=False, reason="game_over")

        validation = self._rule_engine.validate_move(
            self._board, from_row, from_col, to_row, to_col
        )
        if not validation.is_valid:
            return MoveResult(is_accepted=False, reason=validation.reason)

        piece = self._board.get_cell(from_row, from_col)
        new_route = get_move_route(from_row, from_col, to_row, to_col, piece.piece_type)
        new_from = (from_row, from_col)
        new_to = (to_row, to_col)

        for existing in self._active_moves:
            if is_route_conflict(
                existing["from"],
                existing["to"],
                existing["route"],
                new_from,
                new_to,
                new_route,
                existing["color"],
                piece.color,
                existing_jump=existing.get("jump", False),
            ):
                return MoveResult(is_accepted=False, reason="route_conflict")

        self._active_moves.append(
            {
                "from": new_from,
                "to": new_to,
                "remaining": self._move_durations[piece.piece_type] * len(new_route),
                "order": self._next_order,
                "route": new_route,
                "color": piece.color,
            }
        )
        self._next_order += 1
        return MoveResult(is_accepted=True, reason="ok")

    def request_jump(self, from_row, from_col):
        """Schedule an airborne jump from the given cell."""
        if self._state.is_game_over:
            return MoveResult(is_accepted=False, reason="game_over")

        piece = self._board.get_cell(from_row, from_col)
        if piece is None:
            return MoveResult(is_accepted=False, reason="empty_source")

        self._active_moves.append(
            {
                "from": (from_row, from_col),
                "to": (from_row, from_col),
                "remaining": self._jump_duration_ms,
                "order": self._next_order,
                "route": [],
                "color": piece.color,
                "jump": True,
            }
        )
        self._next_order += 1
        return MoveResult(is_accepted=True, reason="ok")

    def snapshot(self):
        """Return a read-only view of current logical game state."""
        pieces = []
        for row in range(self._board.num_rows):
            for col in range(self._board.num_cols):
                piece = self._board.get_cell(row, col)
                if piece is not None:
                    pieces.append((row, col, piece.token, piece.piece_id))
        return GameSnapshot(
            board_width=self._board.num_cols,
            board_height=self._board.num_rows,
            game_over=self._state.is_game_over,
            selected=self._state.selected,
            pieces=tuple(pieces),
        )
