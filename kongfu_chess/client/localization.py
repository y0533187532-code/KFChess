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
    "role_player": "Player",
    "role_spectator": "Spectator",
    "seat_first_player": "First player",
    "seat_second_player": "Second player",
    "room_status_waiting": "Waiting",
    "room_status_active": "Active",
    "room_status_closed": "Closed",
    "room_status_interrupted": "Interrupted",
    "room_status_ended": "Ended",
    "waiting_for_opponent": "Waiting for an opponent...",
    "chess_color_white": "White",
    "chess_color_black": "Black",
    "spectator": "Spectator (no player color)",
    "spectator_read_only": "Spectator mode — view only",
    "players": "Players: {count}",
    "spectators": "Spectators: {count}",
    "refresh": "Refresh",
    "leave_room": "Leave room",
    "real_time_play": "Real-time play",
    "game_state_created": "Game created",
    "game_state_waiting": "Waiting for game state",
    "game_state_active": "Game active",
    "game_state_reconnecting": "Paused for reconnect",
    "game_state_ended": "Game ended",
    "game_state_cancelled": "Game cancelled",
    "game_state_interrupted": "Game interrupted",
    "reconnect_countdown": "Paused for reconnect: {seconds}s remaining",
    "game_won_message": "You won the game.",
    "game_lost_message": "You lost the game.",
    "game_ended_message": "The game ended.",
    "game_cancelled_message": "The game was cancelled.",
    "game_interrupted_message": "The game was interrupted.",
    "invalid_snapshot": "The server returned an invalid game state.",
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
