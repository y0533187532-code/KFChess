import pytest

from kongfu_chess.server import (
    CHESS_SEAT_ADAPTER,
    PLAY_GAME_MODE,
    ROOM_GAME_MODE,
    ChessColor,
    ChessOutcome,
    GameMode,
    GameModeConfig,
    GameRole,
    MatchOutcome,
    PlayerSeat,
    SeatAssignmentPolicy,
)


def test_mvp_modes_declare_neutral_player_seats():
    expected_seats = (PlayerSeat.FIRST_PLAYER, PlayerSeat.SECOND_PLAYER)
    assert PLAY_GAME_MODE.player_seats == expected_seats
    assert PLAY_GAME_MODE.mode is GameMode.PLAY
    assert PLAY_GAME_MODE.ranked is True
    assert ROOM_GAME_MODE.player_seats == PLAY_GAME_MODE.player_seats
    assert ROOM_GAME_MODE.mode is GameMode.ROOM
    assert ROOM_GAME_MODE.ranked is False
    assert GameRole.SPECTATOR.value == "SPECTATOR"


def test_assignment_policy_maps_selector_order_to_configured_seats():
    policy = SeatAssignmentPolicy(lambda players: tuple(reversed(players)))

    assignments = policy.assign((10, 20), PLAY_GAME_MODE)

    assert tuple(item.user_id for item in assignments) == (20, 10)
    assert tuple(item.seat for item in assignments) == PLAY_GAME_MODE.player_seats


def test_assignment_policy_rejects_wrong_player_count_or_invalid_selection():
    policy = SeatAssignmentPolicy(lambda players: (players[0], players[0]))

    with pytest.raises(ValueError, match="Player count"):
        policy.assign((10,), PLAY_GAME_MODE)
    with pytest.raises(ValueError, match="every player"):
        policy.assign((10, 20), PLAY_GAME_MODE)


def test_game_mode_config_rejects_missing_or_duplicate_player_seats():
    with pytest.raises(ValueError, match="at least one"):
        GameModeConfig(GameMode.PLAY, (), ranked=True)
    with pytest.raises(ValueError, match="unique"):
        GameModeConfig(
            GameMode.PLAY,
            (PlayerSeat.FIRST_PLAYER, PlayerSeat.FIRST_PLAYER),
            ranked=True,
        )


def test_chess_adapter_is_the_white_black_compatibility_boundary():
    assert (
        CHESS_SEAT_ADAPTER.color_for_player(PlayerSeat.FIRST_PLAYER)
        is ChessColor.WHITE
    )
    assert (
        CHESS_SEAT_ADAPTER.color_for_player(PlayerSeat.SECOND_PLAYER)
        is ChessColor.BLACK
    )
    assert (
        CHESS_SEAT_ADAPTER.persistence_color(GameRole.SPECTATOR, None)
        is None
    )
    assert (
        CHESS_SEAT_ADAPTER.match_outcome(ChessOutcome.WHITE_WIN)
        is MatchOutcome.FIRST_PLAYER_WIN
    )
    assert (
        CHESS_SEAT_ADAPTER.match_outcome(ChessOutcome.BLACK_WIN)
        is MatchOutcome.SECOND_PLAYER_WIN
    )
