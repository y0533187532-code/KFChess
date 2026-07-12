"""Game facade: click/wait protocol wiring Controller and GameEngine."""

try:
    from .engine.game_engine import GameEngine, default_promotion_policy
    from .input.controller import Controller
    from .model.game_state import GameState
    from .rules import PieceRules, RuleEngine, validate_promotion_piece_type
except ImportError:
    from engine.game_engine import GameEngine, default_promotion_policy
    from input.controller import Controller
    from model.game_state import GameState
    from rules import PieceRules, RuleEngine, validate_promotion_piece_type


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
            promotion_policy=promotion_policy,
            game_over_piece_type=game_over_piece_type,
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

    @property
    def _rule_engine(self):
        return self._engine.rule_engine

    def handle_click(self, pixel_x, pixel_y):
        self._controller.click(pixel_x, pixel_y)

    def handle_promote(self, piece_type):
        if self._state.is_game_over:
            return
        piece_rules = self._engine.rule_engine.piece_rules
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
        self._engine.wait(milliseconds)


__all__ = ["Game", "default_promotion_policy"]
