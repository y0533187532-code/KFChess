from kongfu_chess.config import CELL_SIZE_PX

from ..board.board_coordinates import cell_to_pixels


JUMP_HEIGHT_PX = CELL_SIZE_PX // 2


class PiecePositioner:
    """Calculate where a piece should be drawn on the board."""

    def find_active_move_for_piece(
        self,
        piece,
        active_moves: list[dict],
    ) -> dict | None:
        """Return the active motion record for this piece, if it exists."""
        for move in active_moves:
            moving_piece = move.get("piece")
            if moving_piece is not None and moving_piece.piece_id != piece.piece_id:
                continue
            move_row, move_col = move["from"]
            if (piece.row, piece.col) == (move_row, move_col):
                return move
        return None

    def pixel_position_for_piece(
        self,
        piece,
        active_move: dict | None,
    ) -> tuple[int, int]:
        """Return the top-left pixel position for the piece on the board."""
        if active_move is None:
            return cell_to_pixels(piece.row, piece.col)

        from_row, from_col = active_move["from"]
        to_row, to_col = active_move["to"]

        start_x, start_y = cell_to_pixels(from_row, from_col)
        end_x, end_y = cell_to_pixels(to_row, to_col)

        total_ms = active_move["total_ms"]
        remaining_ms = active_move["remaining"]
        if total_ms <= 0:
            return cell_to_pixels(piece.row, piece.col)

        elapsed_ms = total_ms - remaining_ms
        progress = elapsed_ms / total_ms
        progress = max(0.0, min(1.0, progress))

        x = int(start_x + (end_x - start_x) * progress)
        y = int(start_y + (end_y - start_y) * progress)
        if active_move.get("jump"):
            y -= self._jump_offset(progress)

        return x, y

    def _jump_offset(self, progress: float) -> int:
        """Return how high the piece should visually rise during a jump."""
        return int(JUMP_HEIGHT_PX * (1 - abs(0.5 - progress) * 2))
