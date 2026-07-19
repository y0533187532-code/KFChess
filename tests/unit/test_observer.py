from kongfu_chess.engine import SynchronousEventBus
from kongfu_chess.game import Game
from kongfu_chess.model.board import Board
from kongfu_chess.model.events import (
    GameOverEvent,
    MoveCompletedEvent,
    PieceCapturedEvent,
)


class RecordingSubscriber:
    def __init__(self):
        self.events = []

    def handle(self, event):
        self.events.append(event)


class StateAwareSubscriber:
    def __init__(self, board, state):
        self._board = board
        self._state = state
        self.observations = []

    def handle(self, event):
        self.observations.append(
            {
                "event": event,
                "game_over": self._state.is_game_over,
                "destination_token": self._board.get_cell(*event.position).token,
                "score": dict(self._state.score_by_color),
            }
        )


def test_event_bus_subscribe_is_idempotent_and_unsubscribe_stops_delivery():
    event_bus = SynchronousEventBus()
    subscriber = RecordingSubscriber()
    event = MoveCompletedEvent(1, "wR", (0, 0), (0, 1), (0, 1), "completed")

    event_bus.subscribe(MoveCompletedEvent, subscriber)
    event_bus.subscribe(MoveCompletedEvent, subscriber)
    event_bus.publish(event)
    event_bus.unsubscribe(MoveCompletedEvent, subscriber)
    event_bus.publish(event)

    assert subscriber.events == [event]


def test_move_history_observes_completed_move_events():
    board = Board([["wR", "."]])
    game = Game(board, move_durations={"R": 10})

    game.request_move(0, 0, 0, 1)
    game.handle_wait(10)

    history_event = game.state.move_history.events[-1]
    snapshot_event = game.snapshot().completed_moves[-1]
    assert isinstance(history_event, MoveCompletedEvent)
    assert history_event.actual_to == (0, 1)
    assert snapshot_event.piece_id == history_event.piece_id


def test_capture_event_is_published_after_core_state_is_consistent():
    board = Board([["wR", "bP"]])
    game = Game(board, move_durations={"R": 10})
    subscriber = StateAwareSubscriber(board, game.state)
    game.subscribe(PieceCapturedEvent, subscriber)

    game.request_move(0, 0, 0, 1)
    game.handle_wait(10)

    observation = subscriber.observations[-1]
    assert observation["destination_token"] == "wR"
    assert observation["score"] == {"w": 1, "b": 0}
    assert observation["event"].captured_token == "bP"
    assert observation["event"].points_awarded == 1


def test_king_capture_publishes_game_over_after_state_is_marked():
    board = Board([["wR", "bK"]])
    game = Game(board, move_durations={"R": 10})
    subscriber = RecordingSubscriber()
    game.subscribe(GameOverEvent, subscriber)

    game.request_move(0, 0, 0, 1)
    game.handle_wait(10)

    assert game.is_game_over is True
    assert subscriber.events == [
        GameOverEvent(
            winning_color="w",
            captured_piece_id=game.state.captured_pieces[-1].piece_id,
        )
    ]
