"""Protocol handlers for authentication messages; no UI or socket logic."""

from __future__ import annotations

from ..protocol import MessageType, ProtocolError, ProtocolErrorCode
from .auth_service import AuthError
from .event_logger import ServerEventLogger
from .routing import OutgoingMessage


class AuthHandlers:
    def __init__(self, auth_service, *, clock_ms, events: ServerEventLogger | None = None):
        self._auth_service = auth_service
        self._clock_ms = clock_ms
        self._events = events or ServerEventLogger(None)

    def register_routes(self, router) -> None:
        router.register(MessageType.REGISTER_REQUEST.value, self.register)
        router.register(MessageType.LOGIN_REQUEST.value, self.login)
        router.register(MessageType.LOGOUT_REQUEST.value, self.logout)
        router.register(MessageType.VALIDATE_AUTH_REQUEST.value, self.validate)
        router.register(MessageType.DELETE_ACCOUNT_REQUEST.value, self.delete_account)

    def register(self, context) -> OutgoingMessage:
        payload = self._payload(
            context, {"username", "password", "email", "phone"}
        )
        outgoing = self._execute(
            lambda: self._registered(
                self._auth_service.register(
                    username=payload["username"],
                    password=payload["password"],
                    email=payload["email"],
                    phone=payload["phone"],
                    now_ms=self._clock_ms(),
                )
            )
        )
        self._log_auth(context, "register", outgoing)
        return outgoing

    def login(self, context) -> OutgoingMessage:
        payload = self._payload(context, {"username", "password"})
        outgoing = self._execute(
            lambda: self._authenticated(
                self._auth_service.login(
                    username=payload["username"],
                    password=payload["password"],
                    now_ms=self._clock_ms(),
                )
            )
        )
        self._log_auth(context, "login", outgoing)
        return outgoing

    def logout(self, context) -> OutgoingMessage:
        payload = self._payload(context, {"auth_token"})

        def action():
            self._auth_service.logout(payload["auth_token"], now_ms=self._clock_ms())
            return self._success()

        return self._execute(action)

    def validate(self, context) -> OutgoingMessage:
        payload = self._payload(context, {"auth_token"})
        return self._execute(
            lambda: self._principal(
                self._auth_service.validate_auth_token(
                    payload["auth_token"], now_ms=self._clock_ms()
                )
            )
        )

    def delete_account(self, context) -> OutgoingMessage:
        payload = self._payload(context, {"auth_token"})

        def action():
            user_id = self._auth_service.anonymize_account(
                payload["auth_token"], now_ms=self._clock_ms()
            )
            return self._success({"user_id": user_id})

        return self._execute(action)

    @staticmethod
    def _payload(context, expected_fields: set[str]):
        payload = context.envelope.payload
        if set(payload) != expected_fields or not all(
            isinstance(payload[field], str) for field in expected_fields
        ):
            raise ProtocolError(
                ProtocolErrorCode.INVALID_FIELD,
                "Authentication payload does not match its schema",
            )
        return payload

    @classmethod
    def _execute(cls, action) -> OutgoingMessage:
        try:
            return action()
        except AuthError as exc:
            return OutgoingMessage(
                MessageType.COMMAND_RESULT.value,
                {"accepted": False, "code": exc.code.value},
            )

    @staticmethod
    def _success(values=None) -> OutgoingMessage:
        return OutgoingMessage(
            MessageType.COMMAND_RESULT.value,
            {"accepted": True, "code": "ok", **(values or {})},
        )

    @classmethod
    def _registered(cls, account) -> OutgoingMessage:
        return cls._success(
            {
                "user_id": account.user_id,
                "username": account.username,
                "rating": account.rating,
            }
        )

    @classmethod
    def _authenticated(cls, session) -> OutgoingMessage:
        return cls._success(
            {
                "user_id": session.user_id,
                "username": session.username,
                "rating": session.rating,
                "auth_token": session.auth_token,
                "expires_at_ms": session.expires_at_ms,
            }
        )

    @classmethod
    def _principal(cls, principal) -> OutgoingMessage:
        return cls._success(
            {
                "user_id": principal.user_id,
                "username": principal.username,
                "rating": principal.rating,
            }
        )

    def _log_auth(self, context, action: str, outgoing: OutgoingMessage) -> None:
        payload = outgoing.payload
        accepted = payload.get("accepted")
        event = f"auth_{action}_{'succeeded' if accepted else 'failed'}"
        fields = {
            "request_id": context.envelope.request_id,
            "connection_id": context.connection_id,
            "accepted": accepted,
        }
        if payload.get("code"):
            fields["code"] = payload["code"]
        if accepted and payload.get("user_id") is not None:
            fields["user_id"] = payload["user_id"]
        self._events.event(event, **fields)
