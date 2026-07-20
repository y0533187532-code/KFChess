"""Protocol vocabulary only; action payload schemas remain deliberately open."""

from enum import Enum


class MessageType(str, Enum):
    REGISTER_REQUEST = "register_request"
    LOGIN_REQUEST = "login_request"
    LOGOUT_REQUEST = "logout_request"
    PLAY_REQUEST = "play_request"
    CANCEL_MATCHMAKING = "cancel_matchmaking"
    CREATE_ROOM_REQUEST = "create_room_request"
    JOIN_ROOM_REQUEST = "join_room_request"
    LEAVE_ROOM_REQUEST = "leave_room_request"
    RECONNECT_REQUEST = "reconnect_request"
    RESYNC_REQUEST = "resync_request"
    MOVE_REQUEST = "move_request"
    JUMP_REQUEST = "jump_request"
    COMMAND_RESULT = "command_result"
    STATE_UPDATE = "state_update"
    SNAPSHOT = "snapshot"
    GAME_OVER = "game_over"
    ERROR = "error"


SUPPORTED_MESSAGE_TYPES = frozenset(item.value for item in MessageType)
