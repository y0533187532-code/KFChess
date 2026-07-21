"""Builders for client requests using the shared protocol envelope."""

from __future__ import annotations

import time
import uuid

from ..protocol import MessageEnvelope, MessageType


class ClientMessageFactory:
    def __init__(self, policy, *, clock_ms=None, request_id_factory=None):
        self._policy = policy
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._request_id_factory = request_id_factory or (lambda: uuid.uuid4().hex)

    def login(self, username: str, password: str) -> MessageEnvelope:
        return self._make(
            MessageType.LOGIN_REQUEST,
            {"username": username, "password": password},
        )

    def register(
        self, username: str, password: str, email: str, phone: str
    ) -> MessageEnvelope:
        return self._make(
            MessageType.REGISTER_REQUEST,
            {
                "username": username,
                "password": password,
                "email": email,
                "phone": phone,
            },
        )

    def logout(self, auth_token: str) -> MessageEnvelope:
        return self._authenticated(MessageType.LOGOUT_REQUEST, auth_token)

    def validate_auth(self, auth_token: str) -> MessageEnvelope:
        return self._authenticated(MessageType.VALIDATE_AUTH_REQUEST, auth_token)

    def play_join(self, auth_token: str) -> MessageEnvelope:
        return self._authenticated(MessageType.PLAY_QUEUE_JOIN, auth_token)

    def play_cancel(self, auth_token: str) -> MessageEnvelope:
        return self._authenticated(MessageType.PLAY_QUEUE_CANCEL, auth_token)

    def play_status(self, auth_token: str) -> MessageEnvelope:
        return self._authenticated(MessageType.PLAY_QUEUE_STATUS, auth_token)

    def room_create(self, auth_token: str) -> MessageEnvelope:
        return self._authenticated(MessageType.ROOM_CREATE, auth_token)

    def room_join(self, auth_token: str, code: str) -> MessageEnvelope:
        return self._make(
            MessageType.ROOM_JOIN,
            {"auth_token": auth_token, "code": code.upper()},
        )

    def room_leave(self, auth_token: str, code: str) -> MessageEnvelope:
        return self._make(
            MessageType.ROOM_LEAVE,
            {"auth_token": auth_token, "code": code.upper()},
        )

    def room_status(self, auth_token: str, code: str) -> MessageEnvelope:
        return self._make(
            MessageType.ROOM_STATUS,
            {"auth_token": auth_token, "code": code.upper()},
        )

    def _authenticated(self, message_type, auth_token: str) -> MessageEnvelope:
        return self._make(message_type, {"auth_token": auth_token})

    def _make(self, message_type, payload) -> MessageEnvelope:
        resolved_type = (
            message_type.value
            if isinstance(message_type, MessageType)
            else str(message_type)
        )
        return MessageEnvelope.from_mapping(
            {
                "protocol_version": self._policy.protocol_version,
                "type": resolved_type,
                "request_id": self._request_id_factory(),
                "timestamp_ms": self._clock_ms(),
                "payload": payload,
            },
            self._policy,
        )
