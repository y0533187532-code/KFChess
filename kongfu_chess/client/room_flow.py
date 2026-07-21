"""Friendly room entry and lobby behavior for the client controller."""

from __future__ import annotations

from ..protocol import MessageType
from .ui_state import ClientScreen, UiAction


class RoomFlow:
    _ACTIONS = {
        UiAction.ROOM,
        UiAction.ROOM_CREATE,
        UiAction.ROOM_JOIN,
        UiAction.ROOM_CANCEL,
        UiAction.ROOM_REFRESH,
        UiAction.ROOM_LEAVE,
    }

    def __init__(self, context):
        self._context = context

    def handle_action(self, action: UiAction) -> bool:
        if action not in self._ACTIONS:
            return False
        if action is UiAction.ROOM:
            self._context.show(ClientScreen.ROOM_ENTRY)
        elif action is UiAction.ROOM_CREATE:
            self._context.submit(
                self._context.messages.room_create(self._auth_token()),
                "room_create",
            )
        elif action is UiAction.ROOM_JOIN:
            self._submit_join()
        elif action is UiAction.ROOM_CANCEL:
            self._context.show(ClientScreen.MAIN_MENU)
        elif action is UiAction.ROOM_REFRESH:
            self._submit_status()
        else:
            self._submit_leave()
        return True

    def handle_success(
        self, operation: str | None, message_type: str, payload
    ) -> bool:
        if message_type != MessageType.ROOM_STATUS.value:
            return False
        if operation == "room_leave":
            self._context.session.clear_room()
            self._context.show(ClientScreen.MAIN_MENU)
            return True
        self._context.session.store_room(payload)
        self._context.state.fields["room_code"] = self._context.session.room.code
        self._context.show(ClientScreen.ROOM_LOBBY)
        return True

    def _submit_join(self) -> None:
        code = self._context.state.fields["room_code"].upper()
        expected_length = self._context.constraints.room_code_length
        if len(code) != expected_length or not code.isalnum():
            self._context.show_error("invalid_room_code_local")
            return
        self._context.submit(
            self._context.messages.room_join(self._auth_token(), code),
            "room_join",
        )

    def _submit_status(self) -> None:
        room = self._context.session.room
        if room is not None:
            self._context.submit(
                self._context.messages.room_status(self._auth_token(), room.code),
                "room_status",
            )

    def _submit_leave(self) -> None:
        room = self._context.session.room
        if room is not None:
            self._context.submit(
                self._context.messages.room_leave(self._auth_token(), room.code),
                "room_leave",
            )

    def _auth_token(self) -> str:
        return self._context.session.require_auth_token()
