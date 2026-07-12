from kongfu_chess.model.position import Position


def test_positions_with_same_coordinates_are_equal():
    assert Position(0, 0) == Position(0, 0)


def test_positions_with_different_coordinates_are_not_equal():
    assert Position(0, 0) != Position(0, 1)
    assert Position(0, 0) != Position(1, 0)


def test_position_repr_is_readable():
    assert repr(Position(2, 3)) == "Position(2, 3)"
