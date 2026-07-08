"""Game-state transitions driven by the click/wait protocol.

A Game only knows how to react to two kinds of events - a click, and time
passing - and how that changes selection/board state. It never touches the
raw board grid directly (encapsulation): it moves pieces only through the
Board's own public API (``get_cell`` / ``in_bounds`` / ``move_piece``).

Move legality is delegated to ``MovementRules`` (shape + path). In-flight
moves are tracked in ``_active_moves``; multiple pieces may travel in
parallel when their routes do not conflict. The board updates only when
``handle_wait`` completes a move. After arrival there is no cooldown yet
(future iteration can hook into ``_execute_move``).

Capturing the enemy king on move completion ends the game; subsequent
``handle_click`` calls are ignored. ``handle_wait`` is unchanged.

``movement_rules`` and ``move_durations`` are constructor parameters
(defaulting to the standard rule-set), the same pattern Board already uses
for ``valid_colors``/``valid_piece_types`` - a future "design your own game"
feature can hand Game custom instances without any change here.
"""

from .config import (
    CELL_SIZE_PX,
    DEFAULT_JUMP_DURATION_MS,
    DEFAULT_MOVE_DURATION_MS,
    KING_PIECE_TYPE,
    PAWN_PIECE_TYPE,
    QUEEN_PIECE_TYPE,
)
from .movement import (
    MovementRules,
    get_move_route,
    is_path_clear,
    is_promotion_row,
    is_route_conflict,
    is_swap_route,
)


class Game:
    def __init__(
        self,
        board,
        movement_rules=None,
        move_durations=None,
        jump_duration_ms=None,
    ):
        self._board = board
        self._movement_rules = movement_rules or MovementRules()
        self._move_durations = dict(
            move_durations if move_durations is not None else DEFAULT_MOVE_DURATION_MS
        )
        self._jump_duration_ms = (
            jump_duration_ms
            if jump_duration_ms is not None
            else DEFAULT_JUMP_DURATION_MS
        )
        self._selected = None  # None, or a (row, col) tuple
        self._active_moves = []
        self._next_order = 0
        self._game_over = False

    @property
    def is_game_over(self):
        return self._game_over

    def handle_click(self, pixel_x, pixel_y):
        """Handle a click at the given pixel coordinates.

        - Ignored entirely once the game is over.
        - Clicking outside the board is ignored.
        - A piece whose origin is currently in-flight cannot be selected.
        - Clicking a piece with nothing selected selects it (if not moving).
        - Clicking an empty cell with nothing selected is ignored.
        - Clicking another friendly piece while one is selected replaces
          the selection (unless that friendly is in-flight).
        - Otherwise, a move is attempted: if legal and route-conflict-free,
          it is queued as in-flight; the selection is cleared either way.
        """
        if self._game_over:
            return

        row, col = self._pixel_to_cell(pixel_x, pixel_y)
        if not self._board.in_bounds(row, col):
            return

        clicked_piece = self._board.get_cell(row, col)
        moving_origins = {move["from"] for move in self._active_moves}

        if self._selected is None:
            if clicked_piece is not None and (row, col) not in moving_origins:
                self._selected = (row, col)
            return

        from_row, from_col = self._selected
        if (from_row, from_col) in moving_origins:
            self._selected = None
            return

        if (row, col) == (from_row, from_col):
            if clicked_piece is None:
                self._selected = None
            else:
                self._attempt_jump(from_row, from_col)
            return

        if clicked_piece is not None and clicked_piece.color == self._selected_piece.color:
            if (row, col) in moving_origins:
                self._selected = None
            else:
                self._selected = (row, col)
        else:
            self._attempt_move_to(row, col)

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
        dr, dc = row - from_row, col - from_col
        target_piece = self._board.get_cell(row, col)

        if not (
            self._movement_rules.is_legal(
                piece.piece_type,
                dr,
                dc,
                color=piece.color,
                target_piece=target_piece,
                board=self._board,
                from_row=from_row,
                from_col=from_col,
                to_row=row,
                to_col=col,
            )
            and self._path_is_clear(piece.piece_type, from_row, from_col, row, col)
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
                "remaining": self._move_durations[piece.piece_type],
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
        promotion = None
        if (
            moving is not None
            and moving.piece_type == PAWN_PIECE_TYPE
            and is_promotion_row(to_row, self._board.num_rows)
        ):
            promotion = QUEEN_PIECE_TYPE
        self._board.move_piece(
            from_row, from_col, to_row, to_col, promotion_piece_type=promotion
        )
        if self._is_enemy_king_capture(captured, move["color"]):
            self._game_over = True

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
            and captured_piece.piece_type == KING_PIECE_TYPE
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

    def _path_is_clear(self, piece_type, from_row, from_col, row, col):
        if not self._movement_rules.requires_clear_path(piece_type):
            return True
        return is_path_clear(self._board, from_row, from_col, row, col)

    def _pixel_to_cell(self, pixel_x, pixel_y):
        return pixel_y // CELL_SIZE_PX, pixel_x // CELL_SIZE_PX
