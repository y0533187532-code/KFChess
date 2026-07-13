"""Timed cell-entry collision resolution for parallel travel motions."""

from .airborne_jump import is_jump_motion


def collect_cell_entry_events(motion, elapsed_after):
    """Return (entry_time, route_index, cell) events not yet processed on this motion."""
    route = motion.get("route") or []
    if not route:
        return []

    cell_ms = motion["cell_ms"]
    cells_entered = motion.get("cells_entered", 0)
    events = []
    for index in range(cells_entered, len(route)):
        entry_time = (index + 1) * cell_ms
        if entry_time <= elapsed_after:
            events.append((entry_time, index, route[index]))
    return events


def motion_total_ms(motion):
    route = motion.get("route") or []
    if is_jump_motion(motion):
        return motion.get("total_ms", motion["remaining"])
    return motion["cell_ms"] * len(route)


def get_cell_occupant(board, cell, active_moves):
    """Return (kind, color, value) where kind is 'board' or 'transit'."""
    row, col = cell
    piece = board.get_cell(row, col)
    if piece is not None:
        return ("board", piece.color, piece)
    for motion in active_moves:
        if is_jump_motion(motion):
            continue
        if motion.get("transit_cell") == cell:
            return ("transit", motion["color"], motion)
    return None


def clear_motion_transit(motion):
    motion.pop("transit_cell", None)


def resolve_travel_cell_entry(executor, motion, route_index, cell, active_moves):
    """Process one timed cell entry; return True if the motion ended."""
    motion["cells_entered"] = route_index + 1
    occupant = get_cell_occupant(executor.board, cell, active_moves)

    clear_motion_transit(motion)

    if occupant is None:
        route = motion["route"]
        if route_index == len(route) - 1:
            executor.execute_move(motion)
            return True
        motion["transit_cell"] = cell
        return False

    occ_kind, occ_color, occ_value = occupant
    color = motion["color"]
    route = motion["route"]

    if occ_color == color:
        stop_cell = motion["from"] if route_index == 0 else route[route_index - 1]
        if stop_cell != motion["from"]:
            to_row, to_col = stop_cell
            executor.execute_move_to_cell(motion, to_row, to_col)
        return True

    to_row, to_col = cell
    if occ_kind == "transit":
        executor.cancel_motion(occ_value, captured_at=cell)
    executor.execute_move_to_cell(motion, to_row, to_col)
    return True
