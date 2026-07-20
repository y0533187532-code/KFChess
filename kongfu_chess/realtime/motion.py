"""In-flight motion records owned by RealTimeArbiter."""

try:
    from .movement_policy import MovementMode
except ImportError:
    from realtime.movement_policy import MovementMode


def make_travel_motion(from_pos, to_pos, remaining_ms, order, route, color):
    """Build a motion dict for a piece traveling along ``route``."""
    return {
        "from": from_pos,
        "to": to_pos,
        "remaining": remaining_ms,
        "order": order,
        "route": route,
        "color": color,
        "movement_mode": MovementMode.GROUNDED,
    }


def make_airborne_travel_motion(
    piece, from_pos, to_pos, remaining_ms, order, color
):
    """Build a destination-only motion whose piece is detached from the board."""
    return {
        "from": from_pos,
        "to": to_pos,
        "remaining": remaining_ms,
        "order": order,
        "route": [],
        "color": color,
        "piece": piece,
        "movement_mode": MovementMode.AIRBORNE,
    }


def make_jump_motion(from_pos, remaining_ms, order, color, piece=None):
    """Build a motion dict for an airborne jump."""
    motion = {
        "from": from_pos,
        "to": from_pos,
        "remaining": remaining_ms,
        "order": order,
        "route": [],
        "color": color,
        "jump": True,
    }
    if piece is not None:
        motion["piece"] = piece
    return motion
