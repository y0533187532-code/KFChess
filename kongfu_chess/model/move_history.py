"""Move-history projection maintained as a domain-event subscriber."""

from types import MappingProxyType

try:
    from .events import MoveCompletedEvent
except ImportError:
    from events import MoveCompletedEvent


class MoveHistory:
    """Record completed moves without exposing mutable storage."""

    def __init__(self):
        self._events = []

    @property
    def events(self) -> tuple[MoveCompletedEvent, ...]:
        return tuple(self._events)

    @property
    def legacy_events(self) -> tuple:
        """Compatibility view for callers that still consume mapping records."""
        return tuple(
            MappingProxyType(
                {
                    "piece_id": event.piece_id,
                    "token": event.token,
                    "from": event.from_pos,
                    "requested_to": event.requested_to,
                    "actual_to": event.actual_to,
                    "reason": event.reason,
                }
            )
            for event in self._events
        )

    def handle(self, event) -> None:
        if isinstance(event, MoveCompletedEvent):
            self._events.append(event)
