"""OpenCV-only rendering and hit testing for the client shell screens."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .ui_state import ClientScreen, UiAction


@dataclass(frozen=True)
class UiHit:
    kind: str
    value: object


@dataclass(frozen=True)
class UiRect:
    x: int
    y: int
    width: int
    height: int

    def contains(self, x: int, y: int) -> bool:
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height


class OpenCvClientRenderer:
    WIDTH = 960
    HEIGHT = 640
    _BACKGROUND = (24, 28, 38)
    _PANEL = (38, 44, 58)
    _TEXT = (235, 238, 245)
    _MUTED = (165, 172, 188)
    _ACCENT = (210, 138, 55)
    _ERROR = (90, 105, 245)
    _INPUT = (29, 34, 46)
    _CHESS_COLOR_TEXT = {
        "w": "chess_color_white",
        "b": "chess_color_black",
    }

    def __init__(self, localizer):
        self._text = localizer
        self._targets: list[tuple[UiRect, UiHit]] = []

    def render(self, state, session) -> np.ndarray:
        frame = np.full(
            (self.HEIGHT, self.WIDTH, 3), self._BACKGROUND, dtype=np.uint8
        )
        self._targets = []
        self._label(frame, self._text.text("app_title"), 40, 55, 1.05, self._ACCENT)
        if state.screen is ClientScreen.LOGIN:
            self._auth(frame, state, registration=False)
        elif state.screen is ClientScreen.REGISTER:
            self._auth(frame, state, registration=True)
        elif state.screen is ClientScreen.MAIN_MENU:
            self._main_menu(frame, session)
        elif state.screen is ClientScreen.PLAY_QUEUE:
            self._play_queue(frame, state)
        elif state.screen is ClientScreen.MATCH_FOUND:
            self._match_found(frame, session)
        elif state.screen is ClientScreen.ROOM_ENTRY:
            self._room_entry(frame, state)
        elif state.screen is ClientScreen.ROOM_LOBBY:
            self._room_lobby(frame, session)
        if state.inline_message:
            self._label(frame, state.inline_message, 190, 590, 0.55, self._ERROR)
        if state.loading:
            self._label(
                frame, self._text.text("loading"), 760, 55, 0.6, self._MUTED
            )
        return frame

    def hit_test(self, x: int, y: int) -> UiHit | None:
        return next(
            (hit for rectangle, hit in reversed(self._targets) if rectangle.contains(x, y)),
            None,
        )

    def _auth(self, frame, state, *, registration: bool) -> None:
        self._panel(frame, UiRect(170, 85, 620, 475 if registration else 390))
        title = "register_title" if registration else "login_title"
        self._label(frame, self._text.text(title), 210, 135, 0.85)
        fields = (
            ("username", "username"),
            ("password", "password"),
        )
        if registration:
            fields += (("email", "email"), ("phone", "phone"))
        y = 165
        for field_name, label_key in fields:
            self._input(frame, state, field_name, label_key, y)
            y += 72
        submit = UiAction.SUBMIT_REGISTER if registration else UiAction.SUBMIT_LOGIN
        submit_key = "register" if registration else "login"
        self._button(frame, self._text.text(submit_key), UiRect(210, y + 8, 250, 48), submit)
        alternate = UiAction.SHOW_LOGIN if registration else UiAction.SHOW_REGISTER
        alternate_key = "show_login" if registration else "show_register"
        self._button(
            frame,
            self._text.text(alternate_key),
            UiRect(490, y + 8, 260, 48),
            alternate,
            secondary=True,
        )

    def _main_menu(self, frame, session) -> None:
        self._panel(frame, UiRect(220, 120, 520, 390))
        self._label(frame, self._text.text("main_menu"), 270, 180, 0.9)
        self._label(
            frame,
            self._text.text("welcome", username=session.username or ""),
            270,
            225,
            0.62,
        )
        self._label(
            frame,
            self._text.text("rating", rating=session.rating or 0),
            270,
            260,
            0.55,
            self._MUTED,
        )
        self._button(frame, self._text.text("play"), UiRect(300, 300, 360, 52), UiAction.PLAY)
        self._button(frame, self._text.text("room"), UiRect(300, 370, 360, 52), UiAction.ROOM)
        self._button(
            frame,
            self._text.text("logout"),
            UiRect(300, 440, 360, 44),
            UiAction.LOGOUT,
            secondary=True,
        )

    def _play_queue(self, frame, state) -> None:
        self._panel(frame, UiRect(220, 145, 520, 330))
        self._label(frame, self._text.text("matchmaking"), 280, 215, 0.82)
        self._label(frame, self._text.text("waiting"), 390, 280, 0.65, self._MUTED)
        elapsed = state.queue_seconds_elapsed
        if elapsed is not None:
            self._label(
                frame,
                self._text.text("seconds_waiting", seconds=elapsed),
                345,
                315,
                0.58,
            )
        seconds = state.queue_seconds_remaining
        if seconds is not None:
            self._label(
                frame,
                self._text.text("seconds_remaining", seconds=seconds),
                345,
                345,
                0.58,
            )
        self._button(
            frame,
            self._text.text("cancel"),
            UiRect(330, 375, 300, 52),
            UiAction.PLAY_CANCEL,
            secondary=True,
        )

    def _match_found(self, frame, session) -> None:
        self._panel(frame, UiRect(220, 135, 520, 355))
        self._label(frame, self._text.text("match_found"), 325, 205, 0.9, self._ACCENT)
        game = session.game
        if game is not None:
            self._label(frame, self._text.text("game_id", game_id=game.game_id), 270, 270, 0.52)
            self._label(frame, self._text.text("role", role=game.role), 270, 315, 0.55)
            self._label(
                frame,
                self._text.text(
                    "seat_color",
                    seat=game.seat,
                    color=self._display_chess_color(game.color),
                ),
                270,
                360,
                0.55,
            )

    def _display_chess_color(self, color: str | None) -> str:
        key = self._CHESS_COLOR_TEXT.get(color or "")
        if key is None:
            return color or ""
        return self._text.text(key)

    def _room_entry(self, frame, state) -> None:
        self._panel(frame, UiRect(190, 115, 580, 410))
        self._label(frame, self._text.text("room_title"), 240, 175, 0.9)
        self._button(
            frame,
            self._text.text("create_room"),
            UiRect(240, 215, 480, 52),
            UiAction.ROOM_CREATE,
        )
        self._input(frame, state, "room_code", "room_code", 300)
        self._button(
            frame,
            self._text.text("join_room"),
            UiRect(240, 390, 225, 52),
            UiAction.ROOM_JOIN,
        )
        self._button(
            frame,
            self._text.text("cancel"),
            UiRect(495, 390, 225, 52),
            UiAction.ROOM_CANCEL,
            secondary=True,
        )

    def _room_lobby(self, frame, session) -> None:
        self._panel(frame, UiRect(185, 95, 590, 465))
        room = session.room
        if room is None:
            return
        self._label(frame, self._text.text("room_title"), 230, 150, 0.88)
        lines = (
            self._text.text("room_code_value", code=room.code),
            self._text.text("room_status", status=room.status),
            self._text.text("role", role=room.role),
            self._text.text("players", count=room.player_count),
            self._text.text("spectators", count=room.spectator_count),
        )
        y = 205
        for line in lines:
            self._label(frame, line, 230, y, 0.56)
            y += 38
        ownership = (
            self._text.text("spectator")
            if room.seat is None
            else self._text.text("seat_color", seat=room.seat, color=room.color)
        )
        self._label(frame, ownership, 230, y + 5, 0.54, self._MUTED)
        self._button(
            frame,
            self._text.text("refresh"),
            UiRect(230, 475, 240, 48),
            UiAction.ROOM_REFRESH,
            secondary=True,
        )
        self._button(
            frame,
            self._text.text("leave_room"),
            UiRect(500, 475, 230, 48),
            UiAction.ROOM_LEAVE,
            secondary=True,
        )

    def _input(self, frame, state, field_name: str, label_key: str, y: int) -> None:
        self._label(frame, self._text.text(label_key), 240, y, 0.5, self._MUTED)
        rectangle = UiRect(240, y + 12, 480, 42)
        border = self._ACCENT if state.active_field == field_name else self._MUTED
        cv2.rectangle(
            frame,
            (rectangle.x, rectangle.y),
            (rectangle.x + rectangle.width, rectangle.y + rectangle.height),
            self._INPUT,
            -1,
        )
        cv2.rectangle(
            frame,
            (rectangle.x, rectangle.y),
            (rectangle.x + rectangle.width, rectangle.y + rectangle.height),
            border,
            2,
        )
        self._label(frame, state.display_value(field_name), 252, y + 41, 0.55)
        self._targets.append((rectangle, UiHit("field", field_name)))

    def _button(
        self,
        frame,
        label: str,
        rectangle: UiRect,
        action: UiAction,
        *,
        secondary: bool = False,
    ) -> None:
        color = self._PANEL if secondary else self._ACCENT
        cv2.rectangle(
            frame,
            (rectangle.x, rectangle.y),
            (rectangle.x + rectangle.width, rectangle.y + rectangle.height),
            color,
            -1,
        )
        cv2.rectangle(
            frame,
            (rectangle.x, rectangle.y),
            (rectangle.x + rectangle.width, rectangle.y + rectangle.height),
            self._MUTED,
            1,
        )
        size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0]
        text_x = rectangle.x + max(8, (rectangle.width - size[0]) // 2)
        text_y = rectangle.y + (rectangle.height + size[1]) // 2
        self._label(frame, label, text_x, text_y, 0.55)
        self._targets.append((rectangle, UiHit("action", action)))

    def _panel(self, frame, rectangle: UiRect) -> None:
        cv2.rectangle(
            frame,
            (rectangle.x, rectangle.y),
            (rectangle.x + rectangle.width, rectangle.y + rectangle.height),
            self._PANEL,
            -1,
        )

    def _label(self, frame, text, x, y, scale, color=None) -> None:
        cv2.putText(
            frame,
            str(text),
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color or self._TEXT,
            1,
            cv2.LINE_AA,
        )
