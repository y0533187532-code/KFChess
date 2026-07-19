"""Synchronous typed event publisher for optional domain-event reactions."""

from collections import defaultdict


class SynchronousEventBus:
    """Publish an event to a stable snapshot of its registered subscribers."""

    def __init__(self):
        self._subscribers = defaultdict(list)

    def subscribe(self, event_type, subscriber) -> None:
        subscribers = self._subscribers[event_type]
        if subscriber not in subscribers:
            subscribers.append(subscriber)

    def unsubscribe(self, event_type, subscriber) -> None:
        subscribers = self._subscribers.get(event_type)
        if not subscribers or subscriber not in subscribers:
            return
        subscribers.remove(subscriber)
        if not subscribers:
            self._subscribers.pop(event_type, None)

    def publish(self, event) -> None:
        for subscriber in tuple(self._subscribers.get(type(event), ())):
            subscriber.handle(event)
