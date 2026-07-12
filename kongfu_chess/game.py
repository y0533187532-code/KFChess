"""Game facade: click/wait protocol wiring Controller and GameEngine.

Real-time arrival resolution remains here until Phase 5 extracts RealTimeArbiter.
Board updates on move completion happen in ``handle_wait``.
"""

try:
    from .config import KING_PIECE_TYPE
    from .engine.game_engine import GameEngine
    from .input.controller import Controller
    from .model.game_state import GameState
    from .rules import (
        PieceRules,
        RuleEngine,
        is_swap_route,
        resolve_promotion_piece_type,
        validate_promotion_piece_type,
    )
except ImportError:
    from config import KING_PIECE_TYPE
    from engine.game_engine import GameEngine
    from input.controller import Controller
    from model.game_state import GameState
    from rules import (
        PieceRules,
        RuleEngine,
        is_swap_route,
        resolve_promotion_piece_type,
        validate_promotion_piece_type,
    )


def default_promotion_policy(
    moving_piece, to_row, num_rows, piece_rules, chosen_type=None
):
    """Standard promotion: pawn -> chosen piece, defaulting to Queen on the last row."""
    return resolve_promotion_piece_type(
        moving_piece,
        to_row,
        num_rows,
        piece_rules,
        chosen_type=chosen_type,
    )


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
        rule_engine = rule_engine or RuleEngine(piece_rules)
        self._state = GameState(board=board)
        self._engine = GameEngine(
            board,
            self._state,
            rule_engine=rule_engine,
            move_durations=move_durations,
            jump_duration_ms=jump_duration_ms,
        )
        self._rule_engine = self._engine.rule_engine
        self._promotion_policy = promotion_policy or default_promotion_policy
        self._uses_default_promotion_policy = promotion_policy is None
        self._game_over_piece_type = (
            game_over_piece_type
            if game_over_piece_type is not None
            else KING_PIECE_TYPE
        )
        self._controller = Controller(board, self._state, self._engine)

    @property
    def engine(self):
        return self._engine

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

    @property
    def _active_moves(self):
        return self._engine.active_moves

    def handle_click(self, pixel_x, pixel_y):
        """Handle a click at the given pixel coordinates."""
        self._controller.click(pixel_x, pixel_y)

    def handle_promote(self, piece_type):
        """Set the piece type used for the next pawn promotion."""
        if self._state.is_game_over:
            return
        piece_rules = self._rule_engine.piece_rules
        self._state.set_promotion_choice(
            validate_promotion_piece_type(piece_type, piece_rules)
        )

    def moving_origins(self):
        return self._engine.moving_origins()

    def request_move(self, from_row, from_col, to_row, to_col):
        return self._engine.request_move(from_row, from_col, to_row, to_col)

    def request_move_to(self, row, col):
        from_row, from_col = self._selected
        return self.request_move(from_row, from_col, row, col)

    def request_jump(self, from_row, from_col):
        return self._engine.request_jump(from_row, from_col)

    def snapshot(self):
        return self._engine.snapshot()

    def handle_wait(self, milliseconds):
        """Advance the game clock by ``milliseconds``."""
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
        chosen_type = self._state.consume_promotion_choice()
        piece_rules = self._rule_engine.piece_rules
        if self._uses_default_promotion_policy:
            return resolve_promotion_piece_type(
                moving,
                to_row,
                self._board.num_rows,
                piece_rules,
                chosen_type=chosen_type,
            )
        return self._promotion_policy(
            moving, to_row, self._board.num_rows, chosen_type=chosen_type
        )

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
