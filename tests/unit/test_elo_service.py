from decimal import Decimal

from kongfu_chess.server import EloService, MatchOutcome


def elo():
    return EloService(scale=400, k_factor=32, rating_floor=100)


def test_equal_ratings_win_and_loss_exchange_sixteen_points():
    result = elo().calculate(1200, 1200, MatchOutcome.FIRST_PLAYER_WIN)

    assert result.first_player_rating_after == 1216
    assert result.second_player_rating_after == 1184


def test_higher_rated_player_gains_fewer_points_when_winning():
    result = elo().calculate(1400, 1200, MatchOutcome.FIRST_PLAYER_WIN)

    assert result.first_player_rating_after == 1408
    assert result.second_player_rating_after == 1192


def test_lower_rated_player_gains_more_points_when_winning():
    result = elo().calculate(1200, 1400, MatchOutcome.FIRST_PLAYER_WIN)

    assert result.first_player_rating_after == 1224
    assert result.second_player_rating_after == 1376


def test_draw_moves_ratings_toward_each_other():
    result = elo().calculate(1400, 1200, MatchOutcome.DRAW)

    assert result.first_player_rating_after == 1392
    assert result.second_player_rating_after == 1208


def test_rating_floor_is_applied_after_loss():
    result = elo().calculate(100, 1200, MatchOutcome.SECOND_PLAYER_WIN)

    assert result.first_player_rating_after == 100


def test_half_up_rounds_exact_half_up_and_value_below_half_down():
    assert EloService.round_half_up(Decimal("1200.5")) == 1201
    assert EloService.round_half_up(Decimal("1200.499999")) == 1200


def test_existing_chess_outcome_values_are_supported_at_compatibility_boundary():
    white_win = elo().calculate(1200, 1200, "white_win")
    black_win = elo().calculate(1200, 1200, "black_win")

    assert white_win.first_player_rating_after == 1216
    assert black_win.second_player_rating_after == 1216
