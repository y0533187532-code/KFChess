from kongfu_chess.engine.types import GameSnapshot

from .board_view import cell_to_pixels, load_board, piece_token_to_asset_name
from .img import Img
from .piece_animator import PieceAnimator


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

    def __init__(self) -> None:
        self._animators_by_piece_id: dict[int, PieceAnimator] = {}

    def render(self, snapshot: GameSnapshot, active_moves: list[dict] | None = None) -> Img:
        """Draw the full board from a read-only snapshot."""
        active_moves = active_moves or []
        board = load_board()

        for piece in snapshot.pieces:
            animator = self._get_or_create_animator(
                piece.piece_id,
                piece.token,
                self._asset_state_for(piece.state),
            )
            current_frame = animator.frame_at()
            active_move = self._find_active_move_for_piece(piece, active_moves)

            x, y = cell_to_pixels(piece.row, piece.col)
            current_frame.draw_on(board, x, y)

        return board

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
