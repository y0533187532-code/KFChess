"""Deterministic virtual-time resolution for in-flight motions."""

try:
    from .motion import make_jump_motion, make_travel_motion
except ImportError:
    from motion import make_jump_motion, make_travel_motion


class RealTimeArbiter:
    """Owns active motions; board logical occupancy changes only on arrival."""

    def __init__(self, executor):
        self._executor = executor
        self._active_moves = []
        self._next_order = 0

    @property
    def active_moves(self):
        return self._active_moves

    def has_active_motion(self):
        return bool(self._active_moves)

    def moving_origins(self):
        return {move["from"] for move in self._active_moves}

    def schedule_travel(self, from_pos, to_pos, remaining_ms, route, color):
        motion = make_travel_motion(
            from_pos, to_pos, remaining_ms, self._next_order, route, color
        )
        self._active_moves.append(motion)
        self._next_order += 1
        return motion

    def schedule_jump(self, from_pos, remaining_ms, color):
        motion = make_jump_motion(from_pos, remaining_ms, self._next_order, color)
        self._active_moves.append(motion)
        self._next_order += 1
        return motion

    def advance_time(self, milliseconds):
        """Tick all motions and resolve arrivals in deterministic order."""
        finished = []

        for move in self._active_moves:
            old_remaining = move["remaining"]
            move["remaining"] = old_remaining - milliseconds
            if move["remaining"] <= 0:
                finished.append({"move": move, "finish_time": old_remaining})

        finished.sort(key=lambda item: (item["finish_time"], item["move"]["order"]))

        completed = []
        index = 0
        while index < len(finished):
            finish_time = finished[index]["finish_time"]
            group_end = index
            while (
                group_end < len(finished)
                and finished[group_end]["finish_time"] == finish_time
            ):
                group_end += 1

            group = finished[index:group_end]
            group_moves = [entry["move"] for entry in group]
            airborne_jumps = [
                jump_move
                for jump_move in self._active_moves
                if jump_move.get("jump")
                and (jump_move in group_moves or jump_move["remaining"] > 0)
            ]

            for entry in group:
                move = entry["move"]
                if move not in self._active_moves or move.get("jump"):
                    continue
                if self._executor.is_captured_by_airborne_jump(move, airborne_jumps):
                    from_row, from_col = move["from"]
                    self._executor.clear_source_cell(from_row, from_col)
                    self._remove_active_move(move)
                    completed.append(move)

            for entry in group:
                move = entry["move"]
                if move not in self._active_moves:
                    continue

                if move.get("jump"):
                    self._remove_active_move(move)
                    completed.append(move)
                    continue

                if not self._executor.can_execute_move(move, completed):
                    self._remove_active_move(move)
                    continue

                self._executor.execute_move(move)
                self._remove_active_move(move)
                completed.append(move)

            index = group_end

    def _remove_active_move(self, move):
        while move in self._active_moves:
            self._active_moves.remove(move)
