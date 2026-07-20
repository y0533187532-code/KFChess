"""Airborne jump motion helpers and in-flight capture resolution."""

try:
    from .movement_policy import MovementMode
except ImportError:
    from realtime.movement_policy import MovementMode


def is_jump_motion(motion):
    return motion.get("jump", False)


def is_airborne_travel_motion(motion):
    """True for travel that detached its piece and resolves only on landing."""
    return (
        not is_jump_motion(motion)
        and motion.get("movement_mode") == MovementMode.AIRBORNE
    )


def collect_airborne_jumps(group_moves, active_moves):
    """Return jump motions still airborne during this finish-time group."""
    return [
        jump_move
        for jump_move in active_moves
        if is_jump_motion(jump_move)
        and (jump_move in group_moves or jump_move["remaining"] > 0)
    ]


def is_captured_by_airborne_jump(travel_move, airborne_jumps):
    """True when an arriving traveler is removed by an enemy airborne jump."""
    to_row, to_col = travel_move["to"]
    return any(
        is_jump_motion(jump_move)
        and jump_move["from"] == (to_row, to_col)
        and jump_move["color"] != travel_move["color"]
        for jump_move in airborne_jumps
    )
