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
    "leave_game": "Leave game",
    "leave_game_confirm_title": "Leave the game?",
    "leave_game_confirm_body": "You will forfeit the game.",
    "confirm_leave": "Forfeit and leave",
    "stay_in_game": "Stay in game",
    "game_over_title": "GAME OVER",
    "move_time_column": "Time",
    "move_column": "Move",
    "score_label": "Score",
    "moves_label": "Moves",
    "piece_king": "King",
    "piece_queen": "Queen",
    "piece_rook": "Rook",
    "piece_bishop": "Bishop",
    "piece_knight": "Knight",
    "piece_pawn": "Pawn",
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


HEBREW_CLIENT_TEXT = {
    "app_title": "קונג פו שחמט",
    "login_title": "התחברות",
    "register_title": "יצירת חשבון",
    "username": "שם משתמש",
    "password": "סיסמה",
    "email": "דוא\"ל",
    "phone": "טלפון",
    "login": "התחבר",
    "register": "הרשמה",
    "show_register": "יצירת חשבון חדש",
    "show_login": "חזרה להתחברות",
    "main_menu": "תפריט ראשי",
    "welcome": "שלום, {username}",
    "rating": "דירוג: {rating}",
    "play": "שחק",
    "room": "חדר",
    "logout": "התנתק",
    "matchmaking": "מחפש יריב",
    "waiting": "ממתין...",
    "seconds_waiting": "זמן המתנה: {seconds} שנ'",
    "seconds_remaining": "זמן שנותר: {seconds} שנ'",
    "cancel": "ביטול",
    "match_found": "נמצא משחק",
    "game_id": "משחק: {game_id}",
    "room_title": "חדר",
    "create_room": "צור חדר",
    "join_room": "הצטרף לחדר",
    "room_code": "קוד חדר בן 6 תווים",
    "room_code_value": "קוד חדר: {code}",
    "room_status": "סטטוס: {status}",
    "role": "תפקיד: {role}",
    "seat_color": "מושב: {seat} / צבע: {color}",
    "role_player": "שחקן",
    "role_spectator": "צופה",
    "seat_first_player": "שחקן ראשון",
    "seat_second_player": "שחקן שני",
    "room_status_waiting": "ממתין",
    "room_status_active": "פעיל",
    "room_status_closed": "נסגר",
    "room_status_interrupted": "הופסק",
    "room_status_ended": "הסתיים",
    "waiting_for_opponent": "ממתין ליריב...",
    "chess_color_white": "לבן",
    "chess_color_black": "שחור",
    "spectator": "צופה (ללא צבע)",
    "spectator_read_only": "מצב צפייה בלבד",
    "players": "שחקנים: {count}",
    "spectators": "צופים: {count}",
    "refresh": "רענון",
    "leave_room": "עזוב חדר",
    "leave_game": "יציאה מהמשחק",
    "leave_game_confirm_title": "לצאת מהמשחק?",
    "leave_game_confirm_body": "הפעולה תגרום לויתור על המשחק.",
    "confirm_leave": "ויתור ויציאה",
    "stay_in_game": "המשך לשחק",
    "game_over_title": "GAME OVER",
    "move_time_column": "זמן",
    "move_column": "מהלך",
    "score_label": "ניקוד",
    "moves_label": "מהלכים",
    "piece_king": "מלך",
    "piece_queen": "מלכה",
    "piece_rook": "צריח",
    "piece_bishop": "רץ",
    "piece_knight": "פרש",
    "piece_pawn": "רגלי",
    "real_time_play": "משחק בזמן אמת",
    "game_state_created": "המשחק נוצר",
    "game_state_waiting": "ממתין למצב המשחק",
    "game_state_active": "המשחק פעיל",
    "game_state_reconnecting": "מושהה לחיבור מחדש",
    "game_state_ended": "המשחק הסתיים",
    "game_state_cancelled": "המשחק בוטל",
    "game_state_interrupted": "המשחק הופסק",
    "reconnect_countdown": "מושהה לחיבור מחדש: {seconds} שנ' נותרו",
    "game_won_message": "ניצחת במשחק.",
    "game_lost_message": "הפסדת במשחק.",
    "game_ended_message": "המשחק הסתיים.",
    "game_cancelled_message": "המשחק בוטל.",
    "game_interrupted_message": "המשחק הופסק.",
    "invalid_snapshot": "השרת החזיר מצב משחק לא תקין.",
    "loading": "טוען...",
    "registration_success": "החשבון נוצר. התחבר כדי להמשיך.",
    "network_error": "לא ניתן להגיע לשרת המשחק.",
    "invalid_username_local": "שם משתמש חייב להיות {minimum}-{maximum} אותיות, ספרות או קווים תחתונים.",
    "password_too_short_local": "הסיסמה חייבת להכיל לפחות {minimum} תווים.",
    "invalid_email_local": "הזן כתובת דוא\"ל תקינה.",
    "invalid_phone_local": "הזן מספר טלפון תקין.",
    "invalid_room_code_local": "הזן קוד חדר בן 6 תווים.",
}


_CLIENT_STRINGS = {
    "en": ENGLISH_CLIENT_TEXT,
    "he": HEBREW_CLIENT_TEXT,
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
        if strings is not None:
            self._strings = dict(strings)
        else:
            self._strings = dict(
                _CLIENT_STRINGS.get(language, ENGLISH_CLIENT_TEXT)
            )

    @property
    def language(self) -> str:
        return self._language

    @property
    def is_rtl(self) -> bool:
        return self._language == "he"

    def text(self, key: str, **values) -> str:
        template = self._strings.get(key)
        if template is None and self._protocol_catalog is not None:
            try:
                template = self._protocol_catalog.text(self._language, key)
            except (KeyError, ValueError):
                template = None
        return (template or key).format(**values)

    def view_settings(self):
        from ..config import (
            BISHOP_PIECE_TYPE,
            BLACK_COLOR,
            KING_PIECE_TYPE,
            KNIGHT_PIECE_TYPE,
            PAWN_PIECE_TYPE,
            QUEEN_PIECE_TYPE,
            ROOK_PIECE_TYPE,
            WHITE_COLOR,
        )
        from ..graphics.view_settings import ViewSettings

        return ViewSettings(
            player_names={
                WHITE_COLOR: self.text("chess_color_white"),
                BLACK_COLOR: self.text("chess_color_black"),
            },
            piece_type_names={
                KING_PIECE_TYPE: self.text("piece_king"),
                QUEEN_PIECE_TYPE: self.text("piece_queen"),
                ROOK_PIECE_TYPE: self.text("piece_rook"),
                BISHOP_PIECE_TYPE: self.text("piece_bishop"),
                KNIGHT_PIECE_TYPE: self.text("piece_knight"),
                PAWN_PIECE_TYPE: self.text("piece_pawn"),
            },
            time_column_header=self.text("move_time_column"),
            move_column_header=self.text("move_column"),
            score_label=self.text("score_label"),
            moves_label=self.text("moves_label"),
            rtl=self.is_rtl,
        )
