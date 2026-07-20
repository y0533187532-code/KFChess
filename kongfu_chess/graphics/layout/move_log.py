try:
    from ...engine.reasons import CompletionReason
    from ..view_settings import (
        DEFAULT_MAX_MOVE_LOG_LINES,
        DEFAULT_PIECE_TYPE_NAMES,
        ViewSettings,
    )
except ImportError:
    from engine.reasons import CompletionReason
    from graphics.view_settings import (
        DEFAULT_MAX_MOVE_LOG_LINES,
        DEFAULT_PIECE_TYPE_NAMES,
        ViewSettings,
    )


PIECE_COLOR_INDEX = 0
PIECE_TYPE_INDEX = 1
MAX_MOVE_LOG_LINES = DEFAULT_MAX_MOVE_LOG_LINES
PIECE_TYPE_NAMES = DEFAULT_PIECE_TYPE_NAMES

MOVE_REASON_LABELS = {
    CompletionReason.CAPTURE: " (capture)",
    CompletionReason.SAME_COLOR_BLOCKED: " (blocked)",
}


class MoveLog:
    def __init__(self, settings: ViewSettings | None = None) -> None:
        self._settings = ViewSettings() if settings is None else settings
        self._logged_move_keys: set[tuple] = set()
        self._move_log_by_color = {
            color: [name]
            for color, name in self._settings.player_names.items()
        }

    def lines_by_color(self) -> tuple[list[str], list[str]]:
        first_color, second_color = self._settings.player_colors
        return (
            self._move_log_by_color[first_color],
            self._move_log_by_color[second_color],
        )

    def _cell_name(self, row: int, col: int, board_height: int) -> str:
        file_letter = chr(ord("a") + col)
        rank_number = board_height - row
        return f"{file_letter}{rank_number}"

    def _piece_name(self, token: str) -> str:
        piece_type = token[PIECE_TYPE_INDEX]
        return self._settings.piece_type_names.get(piece_type, token)

    def _format_move_log_line(
        self,
        token: str,
        from_pos: tuple[int, int],
        to_pos: tuple[int, int],
        elapsed_ms: int,
        board_height: int,
        reason: str | None = None,
    ) -> str:
        from_row, from_col = from_pos
        to_row, to_col = to_pos
        seconds = elapsed_ms / 1000
        from_cell = self._cell_name(from_row, from_col, board_height)
        to_cell = self._cell_name(to_row, to_col, board_height)
        piece_name = self._piece_name(token)
        reason_label = MOVE_REASON_LABELS.get(reason, "")

        if reason == CompletionReason.JUMP:
            return f"{seconds:.1f}s {piece_name}: jump {from_cell}"

        return f"{seconds:.1f}s {piece_name}: {from_cell}->{to_cell}{reason_label}"

    def record_new_moves(self, snapshot) -> None:
        completed_moves = getattr(snapshot, "completed_moves", ())
        if completed_moves:
            self._record_completed_moves(snapshot)
            return

        for motion in snapshot.active_motions:
            move_key = (
                motion.from_pos,
                motion.to_pos,
                motion.order,
            )

            if move_key in self._logged_move_keys:
                continue

            piece = self._piece_at(snapshot, motion.from_pos)
            if piece is None:
                continue

            self._logged_move_keys.add(move_key)
            color = piece.token[PIECE_COLOR_INDEX]
            self._move_log_by_color[color].append(
                self._format_move_log_line(
                    piece.token,
                    motion.from_pos,
                    motion.to_pos,
                    snapshot.elapsed_ms,
                    snapshot.board_height,
                )
            )
            self._trim_move_log(color)

    def _record_completed_moves(self, snapshot) -> None:
        for event in snapshot.completed_moves:
            move_key = (
                event.piece_id,
                event.from_pos,
                event.requested_to,
                event.actual_to,
                event.reason,
            )

            if move_key in self._logged_move_keys:
                continue

            self._logged_move_keys.add(move_key)
            color = event.token[PIECE_COLOR_INDEX]
            self._move_log_by_color[color].append(
                self._format_move_log_line(
                    event.token,
                    event.from_pos,
                    event.actual_to,
                    snapshot.elapsed_ms,
                    snapshot.board_height,
                    event.reason,
                )
            )
            self._trim_move_log(color)
            
    def _piece_at(self, snapshot, position: tuple[int, int]):
        row, col = position

        for piece in snapshot.pieces:
            if piece.row == row and piece.col == col:
                return piece

        return None

    def _trim_move_log(self, color: str) -> None:
        lines = self._move_log_by_color[color]
        header = lines[:1]
        moves_without_header = lines[1:]
        latest_moves = moves_without_header[
            -self._settings.max_move_log_lines:
        ]
        self._move_log_by_color[color] = header + latest_moves
