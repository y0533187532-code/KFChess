"""OpenCV-only rendering and hit testing for the client shell screens."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..config import CELL_SIZE_PX
from ..graphics.game_view import GameView
from ..graphics.layout.screen_layout import (
    BACKGROUND_COLOR,
    BOARD_X_PX,
    BOARD_Y_PX,
    HEADER_HEIGHT_PX,
)
from .text_display import prepare_opencv_display_text
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
    _ROLE_TEXT = {
        "PLAYER": "role_player",
        "SPECTATOR": "role_spectator",
    }
    _SEAT_TEXT = {
        "FIRST_PLAYER": "seat_first_player",
        "SECOND_PLAYER": "seat_second_player",
    }
    _ROOM_STATUS_TEXT = {
        "WAITING": "room_status_waiting",
        "ACTIVE": "room_status_active",
        "CLOSED": "room_status_closed",
        "INTERRUPTED": "room_status_interrupted",
        "ENDED": "room_status_ended",
    }
    _LIFECYCLE_TEXT = {
        "CREATED": "game_state_created",
        "WAITING_TO_START": "game_state_waiting",
        "ACTIVE": "game_state_active",
        "PAUSED_FOR_RECONNECT": "game_state_reconnecting",
        "ENDED": "game_state_ended",
        "CANCELLED": "game_state_cancelled",
        "INTERRUPTED": "game_state_interrupted",
    }

    def __init__(self, localizer, *, game_view=None):
        self._text = localizer
        self._game_view = game_view or GameView(
            view_settings=localizer.view_settings()
        )
        self._targets: list[tuple[UiRect, UiHit]] = []

    def render(self, state, session) -> np.ndarray:
        if (
            state.screen is ClientScreen.GAME_BOARD
            and state.game_snapshot is not None
        ):
            return self._game_board(state, session)
        frame = np.full(
            (self.HEIGHT, self.WIDTH, 3), self._BACKGROUND, dtype=np.uint8
        )
        self._targets = []
        if self._text.is_rtl:
            self._label(
                frame,
                self._text.text("app_title"),
                self.WIDTH - 40,
                55,
                1.05,
                self._ACCENT,
                anchor="right",
            )
        else:
            self._label(
                frame, self._text.text("app_title"), 40, 55, 1.05, self._ACCENT
            )
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
            if self._text.is_rtl:
                self._label(
                    frame,
                    state.inline_message,
                    self.WIDTH - 190,
                    590,
                    0.55,
                    self._ERROR,
                    anchor="right",
                )
            else:
                self._label(frame, state.inline_message, 190, 590, 0.55, self._ERROR)
        if state.loading:
            if self._text.is_rtl:
                self._label(
                    frame,
                    self._text.text("loading"),
                    200,
                    55,
                    0.6,
                    self._MUTED,
                )
            else:
                self._label(
                    frame, self._text.text("loading"), 760, 55, 0.6, self._MUTED
                )
        return frame

    def _game_board(self, state, session) -> np.ndarray:
        rendered = self._game_view.render(state.game_snapshot)
        frame = rendered.img
        frame[:HEADER_HEIGHT_PX, :] = BACKGROUND_COLOR
        self._targets = []
        for row in range(state.game_snapshot.board_height):
            for col in range(state.game_snapshot.board_width):
                rectangle = UiRect(
                    BOARD_X_PX + col * CELL_SIZE_PX,
                    BOARD_Y_PX + row * CELL_SIZE_PX,
                    CELL_SIZE_PX,
                    CELL_SIZE_PX,
                )
                self._targets.append(
                    (rectangle, UiHit("board_cell", (row, col)))
                )

        game = session.game
        if game is not None:
            identity = (
                self._text.text("spectator_read_only")
                if game.role == "SPECTATOR"
                else self._text.text(
                    "seat_color",
                    seat=self._display_seat(game.seat),
                    color=self._display_chess_color(game.color),
                )
                if game.seat is not None
                else self._text.text("spectator")
            )
            self._label(
                frame,
                self._text.text("real_time_play"),
                BOARD_X_PX,
                30,
                0.58,
                (25, 25, 25, 255),
            )
            self._label(
                frame,
                identity,
                BOARD_X_PX,
                58,
                0.48,
                (25, 25, 25, 255),
            )
        if state.game_selected_cell is not None:
            row, col = state.game_selected_cell
            cv2.rectangle(
                frame,
                (
                    BOARD_X_PX + col * CELL_SIZE_PX,
                    BOARD_Y_PX + row * CELL_SIZE_PX,
                ),
                (
                    BOARD_X_PX + (col + 1) * CELL_SIZE_PX,
                    BOARD_Y_PX + (row + 1) * CELL_SIZE_PX,
                ),
                (40, 190, 255, 255),
                3,
            )
        lifecycle_key = self._LIFECYCLE_TEXT.get(
            state.game_lifecycle_state or "", "game_state_waiting"
        )
        snapshot = state.game_snapshot
        game_over = snapshot is not None and snapshot.game_over
        lifecycle_terminal = state.game_lifecycle_state in {
            "ENDED",
            "CANCELLED",
            "INTERRUPTED",
        }
        if game_over or lifecycle_terminal:
            lifecycle_text = self._text.text("game_over_title")
        else:
            lifecycle_text = self._text.text(lifecycle_key)
            if state.game_lifecycle_state == "PAUSED_FOR_RECONNECT":
                seconds = state.reconnect_seconds_remaining
                if seconds is not None:
                    lifecycle_text = self._text.text(
                        "reconnect_countdown", seconds=seconds
                    )
        self._label(
            frame,
            lifecycle_text,
            BOARD_X_PX + 430,
            30,
            0.55,
            (25, 25, 25, 255),
        )
        if game_over or lifecycle_terminal:
            self._game_over_banner(frame, state.inline_message)
        leave_rect = UiRect(
            BOARD_X_PX + 240,
            frame.shape[0] - 70,
            220,
            48,
        )
        self._button(
            frame,
            self._text.text("leave_game"),
            leave_rect,
            UiAction.GAME_LEAVE,
            secondary=True,
        )
        if state.game_leave_confirm_pending:
            self._game_leave_confirm_overlay(frame)
        if state.inline_message and not (game_over or lifecycle_terminal):
            self._label(
                frame,
                state.inline_message,
                BOARD_X_PX,
                frame.shape[0] - 25,
                0.5,
                (40, 40, 230, 255),
            )
        return frame

    def _game_over_banner(self, frame, outcome_message: str | None) -> None:
        overlay = frame.copy()
        board_width = 8 * CELL_SIZE_PX
        x = BOARD_X_PX
        y = BOARD_Y_PX + board_width // 2 - 80
        cv2.rectangle(
            overlay,
            (x, y),
            (x + board_width, y + 160),
            (20, 20, 20, 255),
            -1,
        )
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
        self._label(
            frame,
            self._text.text("game_over_title"),
            x + board_width // 2,
            y + 55,
            1.1,
            self._ACCENT,
            anchor="right",
        )
        if outcome_message:
            self._label(
                frame,
                outcome_message,
                x + board_width // 2,
                y + 105,
                0.62,
                self._TEXT,
                anchor="right",
            )

    def _game_leave_confirm_overlay(self, frame) -> None:
        panel = UiRect(BOARD_X_PX + 90, BOARD_Y_PX + 180, 500, 220)
        overlay = frame.copy()
        cv2.rectangle(
            overlay,
            (panel.x, panel.y),
            (panel.x + panel.width, panel.y + panel.height),
            (15, 15, 15, 255),
            -1,
        )
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        cv2.rectangle(
            frame,
            (panel.x, panel.y),
            (panel.x + panel.width, panel.y + panel.height),
            self._MUTED,
            2,
        )
        self._label(
            frame,
            self._text.text("leave_game_confirm_title"),
            panel.x + panel.width // 2,
            panel.y + 45,
            0.75,
            self._TEXT,
            anchor="right",
        )
        self._label(
            frame,
            self._text.text("leave_game_confirm_body"),
            panel.x + panel.width // 2,
            panel.y + 85,
            0.52,
            self._MUTED,
            anchor="right",
        )
        self._button(
            frame,
            self._text.text("confirm_leave"),
            UiRect(panel.x + 30, panel.y + 140, 200, 48),
            UiAction.GAME_LEAVE_CONFIRM,
        )
        self._button(
            frame,
            self._text.text("stay_in_game"),
            UiRect(panel.x + 270, panel.y + 140, 200, 48),
            UiAction.GAME_LEAVE_CANCEL,
            secondary=True,
        )

    def hit_test(self, x: int, y: int) -> UiHit | None:
        return next(
            (hit for rectangle, hit in reversed(self._targets) if rectangle.contains(x, y)),
            None,
        )

    def _auth(self, frame, state, *, registration: bool) -> None:
        panel = UiRect(170, 85, 620, 475 if registration else 390)
        self._panel(frame, panel)
        inner_x = panel.x + 40
        inner_width = panel.width - 80
        title = "register_title" if registration else "login_title"
        self._label(
            frame,
            self._text.text(title),
            inner_x if self._text.is_rtl else 210,
            135,
            0.85,
            box_width=inner_width if self._text.is_rtl else None,
        )
        fields = (
            ("username", "username"),
            ("password", "password"),
        )
        if registration:
            fields += (("email", "email"), ("phone", "phone"))
        y = 165
        for field_name, label_key in fields:
            self._input(
                frame,
                state,
                field_name,
                label_key,
                y,
                panel_x=inner_x,
                panel_width=inner_width,
            )
            y += 72
        submit = UiAction.SUBMIT_REGISTER if registration else UiAction.SUBMIT_LOGIN
        submit_key = "register" if registration else "login"
        alternate = UiAction.SHOW_LOGIN if registration else UiAction.SHOW_REGISTER
        alternate_key = "show_login" if registration else "show_register"
        if self._text.is_rtl:
            self._button(
                frame,
                self._text.text(submit_key),
                UiRect(inner_x + inner_width - 250, y + 8, 250, 48),
                submit,
            )
            self._button(
                frame,
                self._text.text(alternate_key),
                UiRect(inner_x, y + 8, 260, 48),
                alternate,
                secondary=True,
            )
        else:
            self._button(
                frame,
                self._text.text(submit_key),
                UiRect(210, y + 8, 250, 48),
                submit,
            )
            self._button(
                frame,
                self._text.text(alternate_key),
                UiRect(490, y + 8, 260, 48),
                alternate,
                secondary=True,
            )

    def _main_menu(self, frame, session) -> None:
        panel = UiRect(220, 120, 520, 390)
        self._panel(frame, panel)
        inner_x = panel.x + 50
        inner_width = panel.width - 100
        label_x = inner_x if self._text.is_rtl else 270
        self._label(
            frame,
            self._text.text("main_menu"),
            label_x,
            180,
            0.9,
            box_width=inner_width if self._text.is_rtl else None,
        )
        self._label(
            frame,
            self._text.text("welcome", username=session.username or ""),
            label_x,
            225,
            0.62,
            box_width=inner_width if self._text.is_rtl else None,
        )
        self._label(
            frame,
            self._text.text("rating", rating=session.rating or 0),
            label_x,
            260,
            0.55,
            self._MUTED,
            box_width=inner_width if self._text.is_rtl else None,
        )
        self._button(
            frame, self._text.text("play"), UiRect(300, 300, 360, 52), UiAction.PLAY
        )
        self._button(
            frame, self._text.text("room"), UiRect(300, 370, 360, 52), UiAction.ROOM
        )
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
            self._label(
                frame,
                self._text.text("role", role=self._display_role(game.role)),
                270,
                315,
                0.55,
            )
            self._label(
                frame,
                self._text.text(
                    "seat_color",
                    seat=self._display_seat(game.seat),
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

    def _display_role(self, role: str) -> str:
        key = self._ROLE_TEXT.get(role)
        return role if key is None else self._text.text(key)

    def _display_seat(self, seat: str | None) -> str:
        key = self._SEAT_TEXT.get(seat or "")
        if key is None:
            return seat or ""
        return self._text.text(key)

    def _display_room_status(self, status: str) -> str:
        key = self._ROOM_STATUS_TEXT.get(status)
        return status if key is None else self._text.text(key)

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
            self._text.text(
                "room_status", status=self._display_room_status(room.status)
            ),
            self._text.text("role", role=self._display_role(room.role)),
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
            else self._text.text(
                "seat_color",
                seat=self._display_seat(room.seat),
                color=self._display_chess_color(room.color),
            )
        )
        self._label(frame, ownership, 230, y + 5, 0.54, self._MUTED)
        if room.status == "WAITING":
            self._label(
                frame,
                self._text.text("waiting_for_opponent"),
                230,
                y + 43,
                0.54,
                self._MUTED,
            )
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

    def _input(
        self,
        frame,
        state,
        field_name: str,
        label_key: str,
        y: int,
        *,
        panel_x: int = 240,
        panel_width: int = 480,
    ) -> None:
        self._label(
            frame,
            self._text.text(label_key),
            panel_x,
            y,
            0.5,
            self._MUTED,
            box_width=panel_width if self._text.is_rtl else None,
        )
        rectangle = UiRect(panel_x, y + 12, panel_width, 42)
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
        value = state.display_value(field_name)
        rendered_value = self._render_text(value, rtl_display=False)
        value_size, _ = cv2.getTextSize(
            rendered_value, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1
        )
        if self._text.is_rtl:
            value_x = panel_x + panel_width - 12 - value_size[0]
        else:
            value_x = panel_x + 12
        self._label(
            frame,
            value,
            value_x,
            y + 41,
            0.55,
            rtl_display=False,
        )
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
        size = cv2.getTextSize(
            self._render_text(label),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            1,
        )[0]
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

    def _render_text(self, text: str, *, rtl_display: bool | None = None) -> str:
        should_rtl = self._text.is_rtl if rtl_display is None else rtl_display
        return prepare_opencv_display_text(str(text), rtl=should_rtl)

    def _label(
        self,
        frame,
        text,
        x,
        y,
        scale,
        color=None,
        *,
        box_width: int | None = None,
        anchor: str = "left",
        rtl_display: bool | None = None,
    ) -> None:
        rendered = self._render_text(text, rtl_display=rtl_display)
        text_size, _ = cv2.getTextSize(
            rendered, cv2.FONT_HERSHEY_SIMPLEX, scale, 1
        )
        should_rtl = self._text.is_rtl if rtl_display is None else rtl_display
        if should_rtl:
            if box_width is not None:
                x = x + box_width - text_size[0]
            elif anchor == "right":
                x = max(0, x - text_size[0])
        cv2.putText(
            frame,
            rendered,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color or self._TEXT,
            1,
            cv2.LINE_AA,
        )
