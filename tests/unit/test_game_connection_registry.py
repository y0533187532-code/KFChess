from kongfu_chess.server import GameConnectionRegistry


def test_bind_and_lookup_connections():
    registry = GameConnectionRegistry()

    registry.bind("conn-1", "game-1", 10)
    registry.bind("conn-2", "game-1", 20)
    registry.bind("conn-3", "game-2", 30)

    assert registry.connections_for("game-1") == ("conn-1", "conn-2")
    assert registry.connections_for("game-2") == ("conn-3",)
    assert registry.connections_for("missing") == ()


def test_rebind_moves_connection_between_games():
    registry = GameConnectionRegistry()

    registry.bind("conn-1", "game-1", 10)
    registry.bind("conn-1", "game-2", 10)

    assert registry.connections_for("game-1") == ()
    assert registry.connections_for("game-2") == ("conn-1",)


def test_remove_connection_clears_game_mapping():
    registry = GameConnectionRegistry()

    registry.bind("conn-1", "game-1", 10)
    registry.remove_connection("conn-1")

    assert registry.connections_for("game-1") == ()


def test_pop_connection_returns_binding_before_clearing():
    registry = GameConnectionRegistry()

    registry.bind("conn-1", "game-1", 10)
    binding = registry.pop_connection("conn-1")

    assert binding is not None
    assert binding.connection_id == "conn-1"
    assert binding.game_id == "game-1"
    assert binding.user_id == 10
    assert registry.connections_for("game-1") == ()
