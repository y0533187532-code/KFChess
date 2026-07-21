import pytest

from kongfu_chess.persistence import (
    AuthSessionRepository,
    GameTokenRepository,
    RoomRepository,
    SqliteDatabase,
    TokenService,
    UserRepository,
)
from kongfu_chess.protocol import ProtocolErrorCode
from kongfu_chess.server import (
    AuthError,
    AuthService,
    GameRole,
    PasswordHasher,
    PlayerSeat,
    RoomStatus,
    RoomsError,
    RoomsService,
)


def system(tmp_path, *, max_spectators=10, codes=("abc234",)):
    database = SqliteDatabase(tmp_path / "rooms.sqlite3", busy_timeout_ms=1000)
    database.migrate()
    users = UserRepository(database, username_min_length=3, username_max_length=20)
    tokens = TokenService(
        AuthSessionRepository(database), GameTokenRepository(database), token_bytes=32
    )
    auth = AuthService(
        users,
        tokens,
        PasswordHasher(salt_bytes=16, n=1024, r=8, p=1, hash_bytes=32),
        password_min_length=6,
        initial_rating=1200,
        auth_token_ttl_seconds=600,
    )
    code_values = iter(codes)
    game_ids = iter(f"room-game-{index}" for index in range(1, 100))
    rooms = RoomsService(
        auth,
        tokens,
        RoomRepository(database),
        max_spectators=max_spectators,
        max_open_rooms=100,
        code_factory=lambda: next(code_values),
        game_id_factory=lambda: next(game_ids),
        snapshot_provider=lambda game_id: {"game_id": game_id, "sequence": 0},
    )
    return database, users, tokens, auth, rooms


def player(auth, username, *, now_ms=1000):
    account = auth.register(
        username=username,
        password="secret7",
        email=f"{username}@example.test",
        phone="0501234567",
        now_ms=now_ms,
    )
    session = auth.login(username=username, password="secret7", now_ms=now_ms + 1)
    return account.user_id, session.auth_token


def test_creator_opponent_and_later_users_receive_expected_roles(tmp_path):
    _, _, tokens, auth, rooms = system(tmp_path)
    creator_id, creator = player(auth, "Creator")
    opponent_id, opponent = player(auth, "Opponent", now_ms=1100)
    spectator_id, spectator = player(auth, "Viewer", now_ms=1200)

    created = rooms.create(creator, now_ms=2000)
    joined = rooms.join(opponent, "abc234", now_ms=2001)
    watched = rooms.join(spectator, created.code, now_ms=2002)

    assert created.code == "ABC234"
    assert created.status is RoomStatus.WAITING
    assert created.role is GameRole.PLAYER
    assert created.seat is PlayerSeat.FIRST_PLAYER
    assert tokens.verify_game(
        created.game_token, game_id=created.game_id, now_ms=2002
    ).color == "w"
    assert joined.status is RoomStatus.ACTIVE
    assert joined.seat is PlayerSeat.SECOND_PLAYER
    assert tokens.verify_game(
        joined.game_token, game_id=joined.game_id, now_ms=2002
    ).color == "b"
    assert watched.role is GameRole.SPECTATOR
    assert watched.seat is None
    assert watched.player_count == 2
    assert watched.spectator_count == 1
    assert watched.snapshot == {"game_id": watched.game_id, "sequence": 0}
    spectator_token = tokens.verify_game(
        watched.game_token, game_id=watched.game_id, now_ms=2002
    )
    assert spectator_token.user_id == spectator_id
    assert spectator_token.role == "SPECTATOR"
    assert spectator_token.color is None
    assert creator_id != opponent_id != spectator_id


def test_spectator_cap_and_duplicate_membership_are_enforced(tmp_path):
    _, _, _, auth, rooms = system(tmp_path, max_spectators=2)
    _, creator = player(auth, "Creator")
    _, opponent = player(auth, "Opponent", now_ms=1100)
    _, viewer_one = player(auth, "ViewerOne", now_ms=1200)
    _, viewer_two = player(auth, "ViewerTwo", now_ms=1300)
    _, viewer_three = player(auth, "ViewerThree", now_ms=1400)
    room = rooms.create(creator, now_ms=2000)
    rooms.join(opponent, room.code, now_ms=2001)

    with pytest.raises(RoomsError) as duplicate:
        rooms.join(opponent, room.code, now_ms=2002)
    assert duplicate.value.code is ProtocolErrorCode.ALREADY_IN_ROOM

    rooms.join(viewer_one, room.code, now_ms=2003)
    rooms.join(viewer_two, room.code, now_ms=2004)
    with pytest.raises(RoomsError) as full:
        rooms.join(viewer_three, room.code, now_ms=2005)
    assert full.value.code is ProtocolErrorCode.ROOM_FULL


def test_creator_leaving_before_gameplay_closes_room_and_revokes_tokens(tmp_path):
    _, _, tokens, auth, rooms = system(tmp_path)
    _, creator = player(auth, "Creator")
    _, joiner = player(auth, "Joiner", now_ms=1100)
    room = rooms.create(creator, now_ms=2000)

    left = rooms.leave(creator, room.code, now_ms=2001)

    assert left.status is RoomStatus.CLOSED
    assert left.player_count == 0
    assert tokens.verify_game(
        room.game_token, game_id=room.game_id, now_ms=2002
    ) is None
    with pytest.raises(RoomsError) as closed:
        rooms.join(joiner, room.code, now_ms=2002)
    assert closed.value.code is ProtocolErrorCode.ROOM_CLOSED


def test_second_player_leaving_before_gameplay_releases_seat(tmp_path):
    _, _, tokens, auth, rooms = system(tmp_path)
    _, creator = player(auth, "Creator")
    _, second = player(auth, "Second", now_ms=1100)
    replacement_id, replacement = player(auth, "Replacement", now_ms=1200)
    room = rooms.create(creator, now_ms=2000)
    joined = rooms.join(second, room.code, now_ms=2001)

    left = rooms.leave(second, room.code, now_ms=2002)
    replacement_view = rooms.join(replacement, room.code, now_ms=2003)

    assert left.status is RoomStatus.WAITING
    assert left.player_count == 1
    assert tokens.verify_game(
        joined.game_token, game_id=room.game_id, now_ms=2003
    ) is None
    assert replacement_view.status is RoomStatus.ACTIVE
    assert replacement_view.seat is PlayerSeat.SECOND_PLAYER
    assert tokens.verify_game(
        replacement_view.game_token, game_id=room.game_id, now_ms=2003
    ).user_id == replacement_id


def test_active_game_player_leave_is_deferred_to_disconnect_policy(tmp_path):
    _, _, tokens, auth, rooms = system(tmp_path)
    _, creator = player(auth, "Creator")
    _, opponent = player(auth, "Opponent", now_ms=1100)
    room = rooms.create(creator, now_ms=2000)
    joined = rooms.join(opponent, room.code, now_ms=2001)
    assert rooms.mark_gameplay_started(room.room_id, now_ms=2002) is True

    result = rooms.leave(opponent, room.code, now_ms=2003)

    assert result.leave_deferred is True
    assert result.status is RoomStatus.ACTIVE
    assert result.player_count == 2
    assert tokens.verify_game(
        joined.game_token, game_id=room.game_id, now_ms=2003
    ) is not None


def test_closed_and_ended_rooms_reject_new_members(tmp_path):
    _, _, _, auth, rooms = system(
        tmp_path, codes=("ABC234", "DEF567", "GHJ678")
    )
    _, first = player(auth, "First")
    _, second = player(auth, "Second", now_ms=1100)
    _, third = player(auth, "Third", now_ms=1200)
    _, fourth = player(auth, "Fourth", now_ms=1300)
    _, joiner = player(auth, "Joiner", now_ms=1400)

    closed = rooms.create(first, now_ms=2000)
    rooms.leave(first, closed.code, now_ms=2001)
    ended = rooms.create(second, now_ms=2002)
    rooms.join(third, ended.code, now_ms=2003)
    assert rooms.end(ended.room_id, reason="completed", now_ms=2004) is True

    for code in (closed.code, ended.code):
        with pytest.raises(RoomsError) as terminal:
            rooms.join(joiner, code, now_ms=2005)
        assert terminal.value.code is ProtocolErrorCode.ROOM_CLOSED

    # A terminal room no longer prevents its former member from creating another room.
    reopened = rooms.create(fourth, now_ms=2006)
    assert reopened.status is RoomStatus.WAITING


def test_restart_recovery_closes_waiting_interrupts_active_without_elo_impact(tmp_path):
    _, users, tokens, auth, rooms = system(
        tmp_path, codes=("ABC234", "DEF567")
    )
    waiting_id, waiting_user = player(auth, "Waiting")
    active_id, active_user = player(auth, "Active", now_ms=1100)
    _, opponent = player(auth, "Opponent", now_ms=1200)
    waiting = rooms.create(waiting_user, now_ms=2000)
    active = rooms.create(active_user, now_ms=2001)
    joined = rooms.join(opponent, active.code, now_ms=2002)

    assert rooms.recover_after_restart(now_ms=3000) == (1, 1)

    assert rooms._rooms.by_id(waiting.room_id).status == "CLOSED"
    assert rooms._rooms.by_id(active.room_id).status == "INTERRUPTED"
    assert tokens.verify_game(
        waiting.game_token, game_id=waiting.game_id, now_ms=3000
    ) is None
    assert tokens.verify_game(
        joined.game_token, game_id=active.game_id, now_ms=3000
    ) is None
    assert users.by_id(waiting_id).rating == 1200
    assert users.by_id(active_id).rating == 1200


def test_invalid_codes_and_authentication_fail_before_room_access(tmp_path):
    _, _, _, auth, rooms = system(tmp_path)
    _, creator = player(auth, "Creator")
    room = rooms.create(creator, now_ms=2000)

    with pytest.raises(RoomsError) as invalid:
        rooms.join(creator, "ABC-23", now_ms=2001)
    assert invalid.value.code is ProtocolErrorCode.INVALID_ROOM_CODE
    with pytest.raises(AuthError) as unauthorized:
        rooms.status("invalid-token", room.code, now_ms=2001)
    assert unauthorized.value.code is ProtocolErrorCode.INVALID_TOKEN
