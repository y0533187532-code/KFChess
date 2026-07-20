from kongfu_chess.server.password_hasher import PasswordHasher


def hasher():
    return PasswordHasher(salt_bytes=16, n=1024, r=8, p=1, hash_bytes=32)


def test_password_hash_uses_random_salt_and_never_contains_raw_password():
    first = hasher().hash("correct horse")
    second = hasher().hash("correct horse")

    assert first != second
    assert "correct horse" not in first
    assert first.startswith("scrypt$1$")


def test_password_verification_accepts_match_and_rejects_mismatch_or_bad_hash():
    encoded = hasher().hash("correct horse")

    assert hasher().verify("correct horse", encoded) is True
    assert hasher().verify("wrong", encoded) is False
    assert hasher().verify("correct horse", "not-a-password-hash") is False
