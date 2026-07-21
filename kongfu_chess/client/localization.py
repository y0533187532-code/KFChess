"""Centralized client UI strings and protocol-error localization."""

from __future__ import annotations


ENGLISH_CLIENT_TEXT = {
    "app_title": "Kung Fu Chess",
    "login_title": "Sign in",
    "register_title": "Create account",
    "username": "Username",
    "password": "Password",
    "email": "Email",
    "phone": "Phone",
    "login": "Login",
    "register": "Register",
    "show_register": "Create an account",
    "show_login": "Back to login",
    "main_menu": "Main menu",
    "welcome": "Welcome, {username}",
    "rating": "Rating: {rating}",
    "play": "Play",
    "room": "Room",
    "logout": "Logout",
    "matchmaking": "Finding an opponent",
    "waiting": "Waiting...",
    "seconds_waiting": "Waiting time: {seconds}s",
    "seconds_remaining": "Time remaining: {seconds}s",
    "cancel": "Cancel",
    "match_found": "Match found",
    "game_id": "Game: {game_id}",
    "room_title": "Room",
    "create_room": "Create room",
    "join_room": "Join room",
    "room_code": "6-character room code",
    "room_code_value": "Room code: {code}",
    "room_status": "Status: {status}",
    "role": "Role: {role}",
    "seat_color": "Seat: {seat} / Color: {color}",
    "chess_color_white": "White",
    "chess_color_black": "Black",
    "spectator": "Spectator (no player color)",
    "players": "Players: {count}",
    "spectators": "Spectators: {count}",
    "refresh": "Refresh",
    "leave_room": "Leave room",
    "loading": "Loading...",
    "registration_success": "Account created. Please sign in.",
    "network_error": "Cannot reach the game server.",
    "invalid_username_local": "Username must be {minimum}-{maximum} letters, numbers, or underscores.",
    "password_too_short_local": "Password must contain at least {minimum} characters.",
    "invalid_email_local": "Enter a valid email address.",
    "invalid_phone_local": "Enter a valid phone number.",
    "invalid_room_code_local": "Enter a 6-character room code.",
}


class ClientLocalizer:
    def __init__(
        self,
        *,
        language: str = "en",
        protocol_catalog=None,
        strings=None,
    ):
        self._language = language
        self._protocol_catalog = protocol_catalog
        self._strings = dict(ENGLISH_CLIENT_TEXT if strings is None else strings)

    def text(self, key: str, **values) -> str:
        template = self._strings.get(key)
        if template is None and self._protocol_catalog is not None:
            try:
                template = self._protocol_catalog.text(self._language, key)
            except (KeyError, ValueError):
                template = None
        return (template or key).format(**values)
