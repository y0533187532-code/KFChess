from kongfu_chess.config import CELL_SIZE_PX
from kongfu_chess.engine.types import MotionSnapshot

from ..board.board_coordinates import cell_to_pixels


JUMP_HEIGHT_PX = CELL_SIZE_PX // 2


class PiecePositioner:
    """Calculate where a piece should be drawn on the board."""

    def find_active_move_for_piece(
        self,
        piece,
        active_motions: tuple[MotionSnapshot, ...],
    ) -> MotionSnapshot | None:
        """Return the active motion record for this piece, if it exists."""
        for motion in active_motions:
            if motion.piece_id is not None and motion.piece_id != piece.piece_id:
                continue
            move_row, move_col = motion.from_pos
            if (piece.row, piece.col) == (move_row, move_col):
                return motion
        return None

    def pixel_position_for_piece(
        self,
        piece,
        active_motion: MotionSnapshot | None,
    ) -> tuple[int, int]:
        """Return the top-left pixel position for the piece on the board."""
        if active_motion is None:
            return cell_to_pixels(piece.row, piece.col)

        from_row, from_col = active_motion.from_pos
        to_row, to_col = active_motion.to_pos

        start_x, start_y = cell_to_pixels(from_row, from_col)
        end_x, end_y = cell_to_pixels(to_row, to_col)

        total_ms = active_motion.total_ms
        remaining_ms = active_motion.remaining_ms
        if total_ms <= 0:
            return cell_to_pixels(piece.row, piece.col)

        elapsed_ms = total_ms - remaining_ms
        progress = elapsed_ms / total_ms
        progress = max(0.0, min(1.0, progress))

        x = int(start_x + (end_x - start_x) * progress)
        y = int(start_y + (end_y - start_y) * progress)
        if active_motion.is_jump:
            y -= self._jump_offset(progress)

        return x, y

    def _jump_offset(self, progress: float) -> int:
        """Return how high the piece should visually rise during a jump."""
        return int(JUMP_HEIGHT_PX * (1 - abs(0.5 - progress) * 2))
