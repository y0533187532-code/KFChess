"""Game-state transitions driven by the click/wait protocol.

A Game reacts to clicks, time passing (``handle_wait``), and airborne jumps
(same-cell re-click or the ``jump`` command). It never touches the raw board
grid directly (encapsulation): pieces move only through Board's public API.

Move legality is delegated to ``RuleEngine`` (via ``PieceRules``). In-flight
moves live in ``_active_moves``; parallel travel is allowed when routes do
not conflict. The board updates when ``handle_wait`` completes a move or
when an airborne jump captures an arriving enemy.

Capturing the configured game-over piece (default: king) ends the game;
subsequent ``handle_click`` calls are ignored.

Extension hooks (defaults preserve standard Kong-Fu-Chess rules):
- ``piece_rules`` / ``rule_engine`` — custom piece shapes / pawn direction maps
- ``move_durations`` / ``jump_duration_ms`` — travel timings
- ``promotion_policy(moving_piece, to_row, num_rows) -> piece_type | None``
- ``game_over_piece_type`` — which captured piece type ends the game
"""

try:
    from .config import (
        DEFAULT_JUMP_DURATION_MS,
        DEFAULT_MOVE_DURATION_MS,
        DEFAULT_PROMOTION_BY_PIECE_TYPE,
        KING_PIECE_TYPE,
    )
    from .input.controller import Controller
    from .model.game_state import GameState
    from .rules import (
        PieceRules,
        RuleEngine,
        get_move_route,
        is_promotion_row,
        is_route_conflict,
        is_swap_route,
    )
except ImportError:
    from config import (
        DEFAULT_JUMP_DURATION_MS,
        DEFAULT_MOVE_DURATION_MS,
        DEFAULT_PROMOTION_BY_PIECE_TYPE,
        KING_PIECE_TYPE,
    )
    from input.controller import Controller
    from model.game_state import GameState
    from rules import (
        PieceRules,
        RuleEngine,
        get_move_route,
        is_promotion_row,
        is_route_conflict,
        is_swap_route,
    )


def default_promotion_policy(moving_piece, to_row, num_rows):
    """Standard promotion: pawn -> queen on the first or last row."""
    if moving_piece is None or not is_promotion_row(to_row, num_rows):
        return None
    return DEFAULT_PROMOTION_BY_PIECE_TYPE.get(moving_piece.piece_type)


class Game:
    def __init__(
        self,
        board,
        piece_rules=None,
        rule_engine=None,
        move_durations=None,
        jump_duration_ms=None,
        promotion_policy=None,
        game_over_piece_type=None,
    ):
        self._board = board
        piece_rules = piece_rules or PieceRules()
        self._rule_engine = rule_engine or RuleEngine(piece_rules)
        self._move_durations = dict(
            move_durations if move_durations is not None else DEFAULT_MOVE_DURATION_MS
        )
        self._jump_duration_ms = (
            jump_duration_ms
            if jump_duration_ms is not None
            else DEFAULT_JUMP_DURATION_MS
        )
        self._promotion_policy = promotion_policy or default_promotion_policy
        self._game_over_piece_type = (
            game_over_piece_type
            if game_over_piece_type is not None
            else KING_PIECE_TYPE
        )
        self._state = GameState(board=board)
        self._active_moves = []
        self._next_order = 0
        self._controller = Controller(board, self._state, self)

    @property
    def state(self):
        return self._state

    @property
    def is_game_over(self):
        return self._state.is_game_over

    @property
    def _selected(self):
        return self._state.selected

    @_selected.setter
    def _selected(self, value):
        self._state.selected = value

    @property
    def _game_over(self):
        return self._state.game_over

    @_game_over.setter
    def _game_over(self, value):
        self._state.game_over = value

    def handle_click(self, pixel_x, pixel_y):
        """Handle a click at the given pixel coordinates."""
        self._controller.click(pixel_x, pixel_y)

    def moving_origins(self):
        return {move["from"] for move in self._active_moves}

    def request_move_to(self, row, col):
        self._attempt_move_to(row, col)

    def request_jump(self, from_row, from_col):
        self._attempt_jump(from_row, from_col)

    def handle_wait(self, milliseconds):
        """Advance the game clock by ``milliseconds``.

        Ticks down every in-flight move; those that finish are processed in
        groups by (remaining before tick, queue order). Swap partners that
        lose the race are cancelled without landing. Airborne jumps may
        capture enemy pieces that arrive at their cell during the jump.
        """
        finished = []

        for move in self._active_moves:
            old_remaining = move["remaining"]
            move["remaining"] = old_remaining - milliseconds
            if move["remaining"] <= 0:
                finished.append({"move": move, "finish_time": old_remaining})

        finished.sort(key=lambda item: (item["finish_time"], item["move"]["order"]))

        completed = []
        index = 0
        while index < len(finished):
            finish_time = finished[index]["finish_time"]
            group_end = index
            while (
                group_end < len(finished)
                and finished[group_end]["finish_time"] == finish_time
            ):
                group_end += 1

            group = finished[index:group_end]
            group_moves = [entry["move"] for entry in group]
            airborne_jumps = [
                jump_move
                for jump_move in self._active_moves
                if jump_move.get("jump")
                and (jump_move in group_moves or jump_move["remaining"] > 0)
            ]

            for entry in group:
                move = entry["move"]
                if move not in self._active_moves or move.get("jump"):
                    continue
                if self._is_captured_by_airborne_jump(move, airborne_jumps):
                    from_row, from_col = move["from"]
                    self._board.clear_cell(from_row, from_col)
                    self._remove_active_move(move)
                    completed.append(move)

            for entry in group:
                move = entry["move"]
                if move not in self._active_moves:
                    continue

                if move.get("jump"):
                    self._remove_active_move(move)
                    completed.append(move)
                    continue

                if not self._can_execute_move(move, completed):
                    self._remove_active_move(move)
                    continue

                self._execute_move(move)
                self._remove_active_move(move)
                completed.append(move)

            index = group_end

    @property
    def _selected_piece(self):
        row, col = self._selected
        return self._board.get_cell(row, col)

    def _attempt_jump(self, from_row, from_col):
        piece = self._selected_piece
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
        self._selected = None

    def _attempt_move_to(self, row, col):
        from_row, from_col = self._selected
        piece = self._selected_piece

        if not (
            self._rule_engine.validate_move(
                self._board, from_row, from_col, row, col
            ).is_valid
        ):
            self._selected = None
            return

        new_route = get_move_route(from_row, from_col, row, col, piece.piece_type)
        new_from = (from_row, from_col)
        new_to = (row, col)

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
                self._selected = None
                return

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
        self._selected = None

    def _execute_move(self, move):
        from_row, from_col = move["from"]
        to_row, to_col = move["to"]
        captured = self._board.get_cell(to_row, to_col)
        moving = self._board.get_cell(from_row, from_col)
        promotion = self._resolve_promotion(moving, to_row)
        self._board.move_piece(
            from_row, from_col, to_row, to_col, promotion_piece_type=promotion
        )
        if self._is_enemy_king_capture(captured, move["color"]):
            self._state.mark_game_over()

    def _resolve_promotion(self, moving, to_row):
        return self._promotion_policy(moving, to_row, self._board.num_rows)

    def _is_captured_by_airborne_jump(self, move, airborne_jumps):
        to_row, to_col = move["to"]
        return any(
            jump_move["from"] == (to_row, to_col)
            and jump_move["color"] != move["color"]
            for jump_move in airborne_jumps
        )

    def _is_enemy_king_capture(self, captured_piece, moving_color):
        return (
            captured_piece is not None
            and captured_piece.piece_type == self._game_over_piece_type
            and captured_piece.color != moving_color
        )

    def _remove_active_move(self, move):
        while move in self._active_moves:
            self._active_moves.remove(move)

    def _can_execute_move(self, move, completed_moves):
        for other in self._active_moves:
            if other is move:
                continue
            if self._is_swap_with_lower_order(move, other):
                return False

        for other in completed_moves:
            if self._is_swap_with_lower_order(move, other):
                return False

        return True

    def _is_swap_with_lower_order(self, move, other):
        return (
            is_swap_route(
                move["from"], move["to"], move["color"],
                other["from"], other["to"], other["color"],
            )
            and other["order"] < move["order"]
        )
