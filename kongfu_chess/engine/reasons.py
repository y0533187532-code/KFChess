"""Stable vocabulary shared by validation, commands, and event reporting."""


class MoveReason:
    """Namespaced move-result values used at public API boundaries."""

    OK = "ok"
    GAME_OVER = "game_over"
    PIECE_IN_MOTION = "piece_in_motion"
    PIECE_RESTING = "piece_resting"
    OUTSIDE_BOARD = "outside_board"
    EMPTY_SOURCE = "empty_source"
    FRIENDLY_DESTINATION = "friendly_destination"
    ILLEGAL_PIECE_MOVE = "illegal_piece_move"
    PATH_BLOCKED = "path_blocked"
    DESTINATION_RESERVED = "destination_reserved"


class CompletionReason:
    """Namespaced values describing how an accepted action completed."""

    COMPLETED = "completed"
    CAPTURE = "capture"
    SAME_COLOR_BLOCKED = "same_color_blocked"
    JUMP = "jump"
