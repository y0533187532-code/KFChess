from ..board.board_coordinates import cell_to_pixels


class PiecePositioner:
    """Calculate where a piece should be drawn on the board."""

    def find_active_move_for_piece(
        self,
        piece,
        active_moves: list[dict],
    ) -> dict | None:
        """Return the active motion record for this piece, if it exists."""
        for move in active_moves:
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

        return x, y
    
