from types import MappingProxyType

from kongfu_chess.config import DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE
from kongfu_chess.engine.types import GameSnapshot
from kongfu_chess.model.piece import (
    PIECE_STATE_CAPTURED,
    PIECE_STATE_IDLE,
    PIECE_STATE_JUMPING,
    PIECE_STATE_MOVING,
    PIECE_STATE_RESTING,
)
from .layout.move_log import MoveLog
from .board.board_view import (
    draw_legal_destination,
    draw_rest_timer,
    draw_selection,
    load_board,
)
from .core.img import Img
from .pieces.piece_animation_manager import PieceAnimationManager
from .pieces.piece_assets import TOKEN_PIECE_TYPE_INDEX
from .pieces.piece_positioner import PiecePositioner
from .layout.player_panel import PlayerPanel
from .layout.screen_layout import (
    build_screen_canvas,
    draw_board_on_screen,
    draw_side_panel_text,
    draw_status_text,
)


ASSET_STATE_IDLE = "idle"
ASSET_STATE_MOVE = "move"
ASSET_STATE_JUMP = "jump"
ASSET_STATE_LONG_REST = "long_rest"


class GameView:
    """Render the current game snapshot with animated pieces."""

    _STATE_TO_ASSET_STATE = {
        PIECE_STATE_IDLE: ASSET_STATE_IDLE,
        PIECE_STATE_MOVING: ASSET_STATE_MOVE,
        ASSET_STATE_MOVE: ASSET_STATE_MOVE,
        PIECE_STATE_JUMPING: ASSET_STATE_JUMP,
        PIECE_STATE_CAPTURED: ASSET_STATE_IDLE,
        "selected": ASSET_STATE_IDLE,
        PIECE_STATE_RESTING: ASSET_STATE_LONG_REST,
        "short_rest": "short_rest",
        ASSET_STATE_LONG_REST: ASSET_STATE_LONG_REST,
    }

    def __init__(self, rest_durations=None):
        self._animation_manager = PieceAnimationManager()
        self._positioner = PiecePositioner()
        self._move_log = MoveLog()
        self._frame_index = 0
        self._player_panel = PlayerPanel()
        self._rest_durations = MappingProxyType(
            dict(
                DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE
                if rest_durations is None
                else rest_durations
            )
        )

    @property
    def _animators_by_piece_id(self):
        return self._animation_manager.animators_by_piece_id

    def render(self, snapshot: GameSnapshot, active_moves: list[dict] | None = None) -> Img:
        """Draw the full board from a read-only snapshot."""
        active_moves = active_moves or []
        self._move_log.record_new_moves(snapshot, active_moves, self._frame_index)
        board = load_board()

        for piece in snapshot.pieces:
            if piece.state == PIECE_STATE_CAPTURED:
                continue

            current_frame = self._animation_manager.frame_for(
                piece.piece_id,
                piece.token,
                self._asset_state_for(piece.state),
            )
            active_move = self._positioner.find_active_move_for_piece(piece, active_moves)

            x, y = self._positioner.pixel_position_for_piece(piece, active_move)
            current_frame.draw_on(board, x, y)
            if piece.rest_remaining_ms is not None:
                draw_rest_timer(
                    board,
                    piece.row,
                    piece.col,
                    piece.rest_remaining_ms,
                    self._rest_duration_for(piece),
                )

        for row, col in snapshot.legal_destinations:
            draw_legal_destination(board, row, col)

        if snapshot.selected is not None:
            selected_row, selected_col = snapshot.selected
            draw_selection(board, selected_row, selected_col)

        screen = build_screen_canvas()
        draw_board_on_screen(screen, board)
        status_text = self._player_panel.status_text(snapshot, active_moves)
        draw_status_text(screen, status_text)
        white_moves, black_moves = self._move_log.lines_by_color()
        left_text, right_text = self._player_panel.side_panel_lines(
            snapshot,
            white_moves,
            black_moves,
        )
        draw_side_panel_text(screen, left_text, right_text)
        self._frame_index += 1
        return screen

    def _asset_state_for(self, state: str) -> str:
        """Map logical piece states to the available asset state folders."""
        return self._STATE_TO_ASSET_STATE.get(state, ASSET_STATE_IDLE)

    def _rest_duration_for(self, piece) -> int:
        piece_type = piece.token[TOKEN_PIECE_TYPE_INDEX]
        return self._rest_durations.get(piece_type, piece.rest_remaining_ms)
