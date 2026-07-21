import pytest

from kongfu_chess.protocol import ProtocolErrorCode
from kongfu_chess.server import (
    GameRole,
    PlayerSeat,
    RoomCodePolicy,
    RoomsError,
    RoomSeatingPolicy,
)


def test_room_code_policy_normalizes_and_validates_exact_alphanumeric_shape():
    assert RoomCodePolicy.normalize("abc234") == "ABC234"
    assert RoomCodePolicy.validate("ABC234") == "ABC234"
    assert RoomCodePolicy.is_valid("ABC234") is True

    for invalid in ("ABC23", "ABC2345", "ABC-23", "abc234", ""):
        with pytest.raises(RoomsError) as raised:
            RoomCodePolicy.validate(invalid)
        assert raised.value.code is ProtocolErrorCode.INVALID_ROOM_CODE

    with pytest.raises(RoomsError) as raised:
        RoomCodePolicy.normalize(None)
    assert raised.value.code is ProtocolErrorCode.INVALID_ROOM_CODE


def test_room_code_policy_rejects_confusing_characters_only_for_generation():
    assert RoomCodePolicy.normalize("OI0123") == "OI0123"
    assert RoomCodePolicy(lambda: "abc234").generate() == "ABC234"

    for generated in ("OBC234", "AB0234", "ABI234", "ABC231"):
        with pytest.raises(ValueError, match="exclude"):
            RoomCodePolicy(lambda value=generated: value).generate()


def test_room_seating_policy_assigns_neutral_mvp_seats_then_spectators():
    policy = RoomSeatingPolicy()

    creator = policy.assign_creator()
    opponent = policy.assign_joiner(
        {PlayerSeat.FIRST_PLAYER}, gameplay_started=False
    )
    spectator = policy.assign_joiner(
        {PlayerSeat.FIRST_PLAYER, PlayerSeat.SECOND_PLAYER},
        gameplay_started=False,
    )
    late_spectator = policy.assign_joiner(
        {PlayerSeat.FIRST_PLAYER}, gameplay_started=True
    )

    assert (creator.role, creator.seat) == (
        GameRole.PLAYER,
        PlayerSeat.FIRST_PLAYER,
    )
    assert (opponent.role, opponent.seat) == (
        GameRole.PLAYER,
        PlayerSeat.SECOND_PLAYER,
    )
    assert (spectator.role, spectator.seat) == (GameRole.SPECTATOR, None)
    assert (late_spectator.role, late_spectator.seat) == (GameRole.SPECTATOR, None)
