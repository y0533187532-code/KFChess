"""Deterministic virtual-time resolution for in-flight motions."""

try:
    from .airborne_jump import is_jump_motion
    from .collision import (
        clear_motion_transit,
        collect_cell_entry_events,
        motion_total_ms,
        resolve_travel_cell_entry,
    )
    from .motion import make_jump_motion, make_travel_motion
except ImportError:
    from realtime.airborne_jump import is_jump_motion
    from collision import (
        clear_motion_transit,
        collect_cell_entry_events,
        motion_total_ms,
        resolve_travel_cell_entry,
    )
    from realtime.motion import make_jump_motion, make_travel_motion


class RealTimeArbiter:
    """Owns active motions; board logical occupancy changes only on arrival."""

    def __init__(self, executor):
        self._executor = executor
        self._active_moves = []
        self._active_rests = {}
        self._next_order = 0

    @property
    def active_moves(self):
        return self._active_moves

    def has_active_motion(self):
        return bool(self._active_moves)

    @property
    def active_rests(self):
        return self._active_rests

    def moving_origins(self):
        return {move["from"] for move in self._active_moves}

    def is_piece_resting(self, piece_id):
        return piece_id in self._active_rests

    def rest_remaining_ms(self, piece_id):
        return self._active_rests.get(piece_id)

    def start_rest(self, piece_id, remaining_ms):
        if piece_id is None or remaining_ms <= 0:
            return
        self._active_rests[piece_id] = remaining_ms

    def clear_rest(self, piece_id):
        if piece_id is None:
            return
        self._active_rests.pop(piece_id, None)

    def schedule_travel(self, from_pos, to_pos, remaining_ms, route, color):
        cell_ms = remaining_ms // max(1, len(route))
        motion = make_travel_motion(
            from_pos, to_pos, remaining_ms, self._next_order, route, color
        )
        motion["cell_ms"] = cell_ms
        motion["total_ms"] = remaining_ms
        self._active_moves.append(motion)
        self._next_order += 1
        return motion

    def schedule_jump(self, from_pos, remaining_ms, color):
        motion = make_jump_motion(from_pos, remaining_ms, self._next_order, color)
        motion["total_ms"] = remaining_ms
        self._active_moves.append(motion)
        self._next_order += 1
        return motion

    def advance_time(self, milliseconds):
        """Tick all motions and resolve timed cell entries plus jump landings."""
        if milliseconds < 0:
            milliseconds = 0

        if milliseconds:
            self._advance_rests(milliseconds)

        events = []
        seen_motion_ids = set()

        for move in list(self._active_moves):
            move_id = id(move)
            if move_id in seen_motion_ids:
                continue
            seen_motion_ids.add(move_id)

            if is_jump_motion(move):
                finish_time = move["remaining"]
                move["remaining"] = finish_time - milliseconds
                if move["remaining"] <= 0:
                    events.append((finish_time, move["order"], "jump_end", move))
                continue

            total_ms = motion_total_ms(move)
            move["remaining"] = max(0, move["remaining"] - milliseconds)
            elapsed_after = total_ms - move["remaining"]
            for entry_time, route_index, cell in collect_cell_entry_events(
                move, elapsed_after
            ):
                events.append(
                    (entry_time, move["order"], "cell_entry", move, route_index, cell)
                )

        events.sort(key=lambda item: (item[0], item[1]))

        for event in events:
            kind = event[2]
            move = event[3]
            if move not in self._active_moves:
                continue

            if kind == "jump_end":
                clear_motion_transit(move)
                self._complete_jump(move)
                continue

            route_index, cell = event[4], event[5]
            if resolve_travel_cell_entry(
                self._executor, move, route_index, cell, self._active_moves
            ):
                self._remove_active_move(move)

    def _complete_jump(self, move):
        """End an airborne jump; logical board occupancy is unchanged."""
        self._remove_active_move(move)

    def _remove_active_move(self, move):
        clear_motion_transit(move)
        while move in self._active_moves:
            self._active_moves.remove(move)

    def _advance_rests(self, milliseconds):
        expired_piece_ids = []
        for piece_id, remaining in self._active_rests.items():
            remaining_after = remaining - milliseconds
            if remaining_after <= 0:
                expired_piece_ids.append(piece_id)
            else:
                self._active_rests[piece_id] = remaining_after
        for piece_id in expired_piece_ids:
            self._active_rests.pop(piece_id, None)
