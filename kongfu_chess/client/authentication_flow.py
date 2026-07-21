"""Login, registration, and logout behavior for the client controller."""

from __future__ import annotations

import re

from .ui_state import ClientScreen, UiAction


class AuthenticationFlow:
    _USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
    _EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    _PHONE_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")
    _OPERATIONS = {"login", "register", "logout"}
    _ACTIONS = {
        UiAction.SHOW_LOGIN,
        UiAction.SHOW_REGISTER,
        UiAction.SUBMIT_LOGIN,
        UiAction.SUBMIT_REGISTER,
        UiAction.LOGOUT,
    }

    def __init__(self, context):
        self._context = context

    def handle_action(self, action: UiAction) -> bool:
        if action not in self._ACTIONS:
            return False
        if action is UiAction.SHOW_LOGIN:
            self._context.show(ClientScreen.LOGIN)
        elif action is UiAction.SHOW_REGISTER:
            self._context.show(ClientScreen.REGISTER)
        elif action is UiAction.SUBMIT_LOGIN:
            self._submit_login()
        elif action is UiAction.SUBMIT_REGISTER:
            self._submit_registration()
        else:
            self._context.submit(
                self._context.messages.logout(
                    self._context.session.require_auth_token()
                ),
                "logout",
            )
        return True

    def handle_success(self, operation: str | None, payload) -> bool:
        if operation not in self._OPERATIONS:
            return False
        if operation == "login":
            self._context.session.authenticate(payload)
            self._clear_auth_fields()
            self._context.show(ClientScreen.MAIN_MENU)
        elif operation == "register":
            self._clear_auth_fields()
            self._context.show(ClientScreen.LOGIN)
            self._context.show_message("registration_success")
        else:
            self._context.session.clear()
            self._context.show(ClientScreen.LOGIN)
        return True

    def clear_password_for(self, operation: str | None) -> None:
        if operation in {"login", "register"}:
            self._context.state.fields["password"] = ""

    def _submit_login(self) -> None:
        if not self._valid_username() or not self._valid_password():
            return
        fields = self._context.state.fields
        self._context.submit(
            self._context.messages.login(fields["username"], fields["password"]),
            "login",
        )

    def _submit_registration(self) -> None:
        if not self._valid_username() or not self._valid_password():
            return
        fields = self._context.state.fields
        email = fields["email"].strip()
        phone = re.sub(r"[\s()-]", "", fields["phone"])
        if self._EMAIL_PATTERN.fullmatch(email.casefold()) is None:
            self._context.show_error("invalid_email_local")
            return
        if self._PHONE_PATTERN.fullmatch(phone) is None:
            self._context.show_error("invalid_phone_local")
            return
        self._context.submit(
            self._context.messages.register(
                fields["username"], fields["password"], email, phone
            ),
            "register",
        )

    def _valid_username(self) -> bool:
        username = self._context.state.fields["username"]
        constraints = self._context.constraints
        if not (
            constraints.username_min_length
            <= len(username)
            <= constraints.username_max_length
        ) or self._USERNAME_PATTERN.fullmatch(username) is None:
            self._context.show_error(
                "invalid_username_local",
                minimum=constraints.username_min_length,
                maximum=constraints.username_max_length,
            )
            return False
        return True

    def _valid_password(self) -> bool:
        minimum = self._context.constraints.password_min_length
        if len(self._context.state.fields["password"]) < minimum:
            self._context.show_error("password_too_short_local", minimum=minimum)
            return False
        return True

    def _clear_auth_fields(self) -> None:
        for field_name in ("username", "password", "email", "phone"):
            self._context.state.fields[field_name] = ""
