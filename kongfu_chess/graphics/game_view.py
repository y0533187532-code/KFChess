from kongfu_chess.engine.types import GameSnapshot
from .move_log import MoveLog
from .board_view import (
    cell_to_pixels,
    draw_selection,
    load_board,
    piece_token_to_asset_name,
)
from .img import Img
from .piece_animator import PieceAnimator
from .screen_layout import (
    build_screen_canvas,
    draw_board_on_screen,
    draw_side_panel_text,
    draw_status_text,
)



class GameView:
    """Render the current game snapshot with animated pieces."""

    _STATE_TO_ASSET_STATE = {
        "idle": "idle",
        "moving": "move",
        "move": "move",
        "jump": "jump",
        "captured": "idle",
        "selected": "idle",
        "short_rest": "short_rest",
        "long_rest": "long_rest",
    }

    def __init__(self):
        self._animators_by_piece_id: dict[int, PieceAnimator] = {}
        self._move_log = MoveLog()
        self._frame_index = 0

    def render(self, snapshot: GameSnapshot, active_moves: list[dict] | None = None) -> Img:
        """Draw the full board from a read-only snapshot."""
        active_moves = active_moves or []
        self._move_log.record_new_moves(snapshot, active_moves, self._frame_index)
        board = load_board()

        for piece in snapshot.pieces:
            animator = self._get_or_create_animator(
                piece.piece_id,
                piece.token,
                self._asset_state_for(piece.state),
            )
            current_frame = animator.frame_at()
            active_move = self._find_active_move_for_piece(piece, active_moves)

            x, y = self._pixel_position_for_piece(piece, active_move)
            current_frame.draw_on(board, x, y)

        if snapshot.selected is not None:
            selected_row, selected_col = snapshot.selected
            draw_selection(board, selected_row, selected_col)

        screen = build_screen_canvas()
        draw_board_on_screen(screen, board)
        status_text = self._status_text(snapshot, active_moves)
        draw_status_text(screen, status_text)
        left_text, right_text = self._move_log.lines_by_color()
        draw_side_panel_text(screen, left_text, right_text)
        self._frame_index += 1
        return screen

    def _status_text(self, snapshot: GameSnapshot, active_moves: list[dict]) -> str:
        """Build a short UI status line for the current snapshot."""
        if snapshot.game_over:
            return "Game Over"
        if snapshot.selected is not None:
            row, col = snapshot.selected
            return f"Selected: ({row}, {col})"

        if active_moves:
            return f"Active moves: {len(active_moves)}"

        return "Ready"

    def _asset_state_for(self, state: str) -> str:
        """Map logical piece states to the available asset state folders."""
        return self._STATE_TO_ASSET_STATE.get(state, "idle")

    def _get_or_create_animator(
        self,
        piece_id: int,
        piece_token: str,
        state: str,
    ) -> PieceAnimator:
        """Return the animator for one piece, creating or updating it if needed."""
        piece_name = piece_token_to_asset_name(piece_token)
        animator = self._animators_by_piece_id.get(piece_id)

        if animator is None:
            animator = PieceAnimator(piece_name, state)
            self._animators_by_piece_id[piece_id] = animator
            return animator

        if animator.piece_name != piece_name:
            animator = PieceAnimator(piece_name, state)
            self._animators_by_piece_id[piece_id] = animator
            return animator

        if animator.state_name != state:
            animator.change_state(state)

        return animator

    def _find_active_move_for_piece(
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

    def _pixel_position_for_piece(
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



    