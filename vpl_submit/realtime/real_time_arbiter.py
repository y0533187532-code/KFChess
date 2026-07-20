"""Deterministic virtual-time resolution for in-flight motions."""

from types import MappingProxyType

try:
    from .airborne_jump import is_airborne_travel_motion, is_jump_motion
    from .collision import (
        clear_motion_transit,
        collect_cell_entry_events,
        motion_total_ms,
        resolve_travel_cell_entry,
    )
    from .landing_reservation import LandingReservation
    from .motion import (
        make_airborne_travel_motion,
        make_jump_motion,
        make_travel_motion,
    )
except ImportError:
    from realtime.airborne_jump import is_airborne_travel_motion, is_jump_motion
    from collision import (
        clear_motion_transit,
        collect_cell_entry_events,
        motion_total_ms,
        resolve_travel_cell_entry,
    )
    from realtime.landing_reservation import LandingReservation
    from realtime.motion import (
        make_airborne_travel_motion,
        make_jump_motion,
        make_travel_motion,
    )


class RealTimeArbiter:
    """Owns active motions; board logical occupancy changes only on arrival."""

    def __init__(self, executor):
        self._executor = executor
        self._active_moves = []
        self._active_rests = {}
        self._landing_reservations = {}
        self._next_order = 0
        self._elapsed_ms = 0

    @property
    def active_moves(self):
        return self._active_moves

    def has_active_motion(self):
        return bool(self._active_moves)

    @property
    def elapsed_ms(self):
        return self._elapsed_ms

    @property
    def active_rests(self):
        return MappingProxyType(self._active_rests)

    @property
    def landing_reservations(self):
        return MappingProxyType(self._landing_reservations)

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

    def remove_motion(self, motion):
        """Remove a scheduled motion without exposing collection mutation."""
        clear_motion_transit(motion)
        if is_airborne_travel_motion(motion):
            piece = motion.get("piece")
            self.release_landing(
                motion["to"],
                piece_id=None if piece is None else piece.piece_id,
            )
        while motion in self._active_moves:
            self._active_moves.remove(motion)

    def reservation_at(self, destination):
        for (reserved_destination, _color), reservation in (
            self._landing_reservations.items()
        ):
            if reserved_destination == destination:
                return reservation
        return None

    def has_friendly_landing_reservation(self, destination, color):
        return (destination, color) in self._landing_reservations

    def can_reserve_landing(self, destination, color):
        if (destination, color) in self._landing_reservations:
            return False
        for motion in self._active_moves:
            if motion["color"] != color:
                continue
            if destination == motion["to"] or destination in motion.get("route", ()):
                return False
        return True

    def reserve_landing(self, destination, piece):
        if not self.can_reserve_landing(destination, piece.color):
            return False
        self._landing_reservations[(destination, piece.color)] = LandingReservation(
            piece_id=piece.piece_id,
            color=piece.color,
            destination=destination,
        )
        return True

    def release_landing(self, destination, piece_id=None):
        matching_keys = [
            key
            for key, reservation in self._landing_reservations.items()
            if reservation.destination == destination
            and (piece_id is None or reservation.piece_id == piece_id)
        ]
        for key in matching_keys:
            self._landing_reservations.pop(key, None)

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

    def schedule_airborne_travel(
        self, piece, from_pos, to_pos, remaining_ms
    ):
        motion = make_airborne_travel_motion(
            piece,
            from_pos,
            to_pos,
            remaining_ms,
            self._next_order,
            piece.color,
        )
        motion["total_ms"] = remaining_ms
        self._active_moves.append(motion)
        self._next_order += 1
        return motion

    def schedule_jump(self, from_pos, remaining_ms, color, piece=None):
        motion = make_jump_motion(from_pos, remaining_ms, self._next_order, color, piece)
        motion["total_ms"] = remaining_ms
        self._active_moves.append(motion)
        self._next_order += 1
        return motion

    def advance_time(self, milliseconds):
        """Tick all motions and resolve timed cell entries plus jump landings."""
        milliseconds = max(0, milliseconds)
        events = self._collect_timed_events(milliseconds)
        self._process_timeline(milliseconds, events)

    def _collect_timed_events(self, milliseconds):
        """Update motion clocks and return events relative to this time tick."""
        events = []
        seen_motion_ids = set()

        for move in list(self._active_moves):
            move_id = id(move)
            if move_id in seen_motion_ids:
                continue
            seen_motion_ids.add(move_id)

            if is_jump_motion(move):
                remaining_before = move["remaining"]
                move["remaining"] = remaining_before - milliseconds
                if move["remaining"] <= 0:
                    events.append(
                        (
                            max(0, remaining_before),
                            move["order"],
                            "jump_end",
                            move,
                        )
                    )
                continue

            if is_airborne_travel_motion(move):
                remaining_before = move["remaining"]
                move["remaining"] = remaining_before - milliseconds
                if move["remaining"] <= 0:
                    events.append(
                        (
                            max(0, remaining_before),
                            move["order"],
                            "airborne_arrival",
                            move,
                        )
                    )
                continue

            total_ms = motion_total_ms(move)
            remaining_before = move["remaining"]
            elapsed_before = total_ms - remaining_before
            move["remaining"] = max(0, remaining_before - milliseconds)
            elapsed_after = total_ms - move["remaining"]
            for entry_time, route_index, cell in collect_cell_entry_events(
                move, elapsed_after
            ):
                events.append(
                    (
                        max(0, entry_time - elapsed_before),
                        move["order"],
                        "cell_entry",
                        move,
                        route_index,
                        cell,
                    )
                )

        events.sort(key=lambda item: (item[0], item[1]))
        return events

    def _process_timeline(self, milliseconds, events):
        """Advance rests between events so new rests start at their event time."""
        elapsed_in_tick = 0
        for event in events:
            event_time = min(milliseconds, max(elapsed_in_tick, event[0]))
            self._advance_timeline(event_time - elapsed_in_tick)
            elapsed_in_tick = event_time
            self._process_timed_event(event)

        self._advance_timeline(milliseconds - elapsed_in_tick)

    def _process_timed_event(self, event):
        kind = event[2]
        move = event[3]
        if move not in self._active_moves:
            return

        if kind == "jump_end":
            clear_motion_transit(move)
            self._complete_jump(move)
            return

        if kind == "airborne_arrival":
            self._complete_airborne_travel(move)
            return

        route_index, cell = event[4], event[5]
        if resolve_travel_cell_entry(
            self._executor,
            move,
            route_index,
            cell,
            self._active_moves,
            tuple(self._landing_reservations.values()),
        ):
            self._remove_active_move(move)

    def _complete_jump(self, move):
        """End an airborne jump; logical board occupancy is unchanged."""
        if hasattr(self._executor, "complete_jump"):
            self._executor.complete_jump(move)
        self._remove_active_move(move)

    def _complete_airborne_travel(self, move):
        if hasattr(self._executor, "complete_airborne_travel"):
            self._executor.complete_airborne_travel(move)
        self._remove_active_move(move)

    def _remove_active_move(self, move):
        self.remove_motion(move)

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

    def _advance_timeline(self, milliseconds):
        self._elapsed_ms += milliseconds
        self._advance_rests(milliseconds)
