import json
from pathlib import Path

import pytest

from kongfu_chess.protocol import (
    EnvelopePolicy,
    LocalizationCatalog,
    MessageEnvelope,
    ProtocolError,
    ProtocolErrorCode,
)


POLICY = EnvelopePolicy(
    protocol_version="1.0",
    max_message_bytes=1024,
    request_id_max_length=64,
    message_type_max_length=32,
)


def valid_document():
    return {
        "protocol_version": "1.0",
        "type": "login_request",
        "request_id": "request-1",
        "timestamp_ms": 123456,
        "payload": {"username": "Dana", "nested": [1, {"ok": True}]},
    }


def test_envelope_round_trip_is_stable_and_payload_is_deeply_immutable():
    envelope = MessageEnvelope.from_mapping(valid_document(), POLICY)

    assert MessageEnvelope.from_json(envelope.to_json(), POLICY) == envelope
    with pytest.raises(TypeError):
        envelope.payload["username"] = "Other"
    with pytest.raises(TypeError):
        envelope.payload["nested"][1]["ok"] = False


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (lambda value: value.pop("request_id"), ProtocolErrorCode.MISSING_FIELD),
        (
            lambda value: value.update(protocol_version="2.0"),
            ProtocolErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
        ),
        (
            lambda value: value.update(type="future_message"),
            ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE,
        ),
        (
            lambda value: value.update(timestamp_ms=-1),
            ProtocolErrorCode.INVALID_FIELD,
        ),
        (
            lambda value: value.update(payload=[]),
            ProtocolErrorCode.INVALID_FIELD,
        ),
    ],
)
def test_envelope_rejects_invalid_contract_with_stable_code(mutation, expected_code):
    document = valid_document()
    mutation(document)

    with pytest.raises(ProtocolError) as raised:
        MessageEnvelope.from_mapping(document, POLICY)

    assert raised.value.code is expected_code


def test_envelope_rejects_invalid_json_and_oversized_message():
    with pytest.raises(ProtocolError) as invalid:
        MessageEnvelope.from_json("{", POLICY)
    assert invalid.value.code is ProtocolErrorCode.INVALID_JSON

    oversized = json.dumps({"padding": "x" * 2048})
    with pytest.raises(ProtocolError) as too_large:
        MessageEnvelope.from_json(oversized, POLICY)
    assert too_large.value.code is ProtocolErrorCode.MESSAGE_TOO_LARGE


def test_every_error_code_has_english_and_hebrew_text():
    locale_directory = Path(__file__).parents[2] / "locales"
    catalog = LocalizationCatalog(locale_directory)

    assert catalog.languages == ("en", "he")
    for code in ProtocolErrorCode:
        assert catalog.text("en", code.value)
        assert catalog.text("he", code.value)
