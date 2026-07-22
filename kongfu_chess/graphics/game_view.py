from types import MappingProxyType

from kongfu_chess.config import DEFAULT_REST_DURATION_MS_BY_PIECE_TYPE
from kongfu_chess.engine.types import GameSnapshot
from kongfu_chess.model.piece_state import PieceState
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
from .view_settings import ViewSettings
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
        PieceState.IDLE: ASSET_STATE_IDLE,
        PieceState.MOVING: ASSET_STATE_MOVE,
        ASSET_STATE_MOVE: ASSET_STATE_MOVE,
        PieceState.JUMPING: ASSET_STATE_JUMP,
        PieceState.CAPTURED: ASSET_STATE_IDLE,
        "selected": ASSET_STATE_IDLE,
        PieceState.RESTING: ASSET_STATE_LONG_REST,
        "short_rest": "short_rest",
        ASSET_STATE_LONG_REST: ASSET_STATE_LONG_REST,
    }

    def __init__(self, rest_durations=None, view_settings=None):
        view_settings = ViewSettings() if view_settings is None else view_settings
        self._view_settings = view_settings
        self._animation_manager = PieceAnimationManager()
        self._positioner = PiecePositioner()
        self._move_log = MoveLog(view_settings)
        self._player_panel = PlayerPanel(view_settings)
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

    def render(self, snapshot: GameSnapshot) -> Img:
        """Draw the full board from a read-only snapshot."""
        self._move_log.record_new_moves(snapshot)
        board = load_board()

        for piece in snapshot.pieces:
            if piece.state == PieceState.CAPTURED:
                continue

            current_frame = self._animation_manager.frame_for(
                piece.piece_id,
                piece.token,
                self._asset_state_for(piece.state),
            )
            active_move = self._positioner.find_active_move_for_piece(
                piece, snapshot.active_motions
            )

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
        status_text = self._player_panel.status_text(snapshot)
        draw_status_text(screen, status_text, rtl=self._view_settings.rtl)
        first_player_moves, second_player_moves = self._move_log.lines_by_color()
        left_text, right_text = self._player_panel.side_panel_lines(
            snapshot,
            first_player_moves,
            second_player_moves,
        )
        draw_side_panel_text(
            screen,
            left_text,
            right_text,
            time_header=self._view_settings.time_column_header,
            move_header=self._view_settings.move_column_header,
            rtl=self._view_settings.rtl,
        )
        return screen

    def _asset_state_for(self, state: PieceState | str) -> str:
        """Map logical piece states to the available asset state folders."""
        return self._STATE_TO_ASSET_STATE.get(state, ASSET_STATE_IDLE)

    def _rest_duration_for(self, piece) -> int:
        piece_type = piece.token[TOKEN_PIECE_TYPE_INDEX]
        return self._rest_durations.get(piece_type, piece.rest_remaining_ms)
