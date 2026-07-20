from .types import (
    GameSnapshot,
    MotionSnapshot,
    MoveEventSnapshot,
    MoveResult,
    MoveValidation,
    PieceSnapshot,
)
from .capture_service import MaterialScorePolicy
from .event_bus import SynchronousEventBus
from .settings import EngineSettings

__all__ = [
    "GameEngine",
    "EngineSettings",
    "MaterialScorePolicy",
    "MotionOutcomeHandler",
    "SynchronousEventBus",
    "GameSnapshot",
    "MotionSnapshot",
    "MoveEventSnapshot",
    "MoveResult",
    "MoveValidation",
    "PieceSnapshot",
]


def __getattr__(name):
    """Load the orchestration facade lazily to keep rules independent of it."""
    if name == "GameEngine":
        from .game_engine import GameEngine

        return GameEngine
    if name == "MotionOutcomeHandler":
        from .motion_outcome_handler import MotionOutcomeHandler

        return MotionOutcomeHandler
    raise AttributeError(name)
