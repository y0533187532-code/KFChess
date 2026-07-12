"""In-flight motion records owned by RealTimeArbiter."""


def make_travel_motion(from_pos, to_pos, remaining_ms, order, route, color):
    """Build a motion dict for a piece traveling along ``route``."""
    return {
        "from": from_pos,
        "to": to_pos,
        "remaining": remaining_ms,
        "order": order,
        "route": route,
        "color": color,
    }


def make_jump_motion(from_pos, remaining_ms, order, color):
    """Build a motion dict for an airborne jump."""
    return {
        "from": from_pos,
        "to": from_pos,
        "remaining": remaining_ms,
        "order": order,
        "route": [],
        "color": color,
        "jump": True,
    }
