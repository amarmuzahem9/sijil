import uuid
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher

from app.core import security


def test_hash_and_verify() -> None:
    h = security.hash_password("correct horse")
    assert h.startswith("$argon2id$")
    assert security.verify_password(h, "correct horse")
    assert not security.verify_password(h, "wrong")
    assert not security.verify_password("not-a-hash", "x")


def test_needs_rehash_for_weaker_parameters() -> None:
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("pw-123456")
    assert security.needs_rehash(weak)
    assert not security.needs_rehash(security.hash_password("pw-123456"))


def test_access_token_roundtrip(frozen_clock) -> None:
    frozen_clock.set(datetime(2026, 11, 21, 10, 0, tzinfo=UTC))
    sid = uuid.uuid4()
    token = security.create_access_token(42, sid)
    assert security.decode_access_token(token) == (42, sid)


def test_access_token_expires_after_15_minutes(frozen_clock) -> None:
    frozen_clock.set(datetime(2026, 11, 21, 10, 0, tzinfo=UTC))
    token = security.create_access_token(1, uuid.uuid4())
    frozen_clock.advance(timedelta(minutes=14, seconds=59))
    security.decode_access_token(token)
    frozen_clock.advance(timedelta(seconds=1))
    with pytest.raises(security.TokenExpired):
        security.decode_access_token(token)


def test_tampered_token_rejected() -> None:
    token = security.create_access_token(1, uuid.uuid4())
    head, payload, sig = token.split(".")
    tampered = ".".join([head, payload, ("A" if sig[0] != "A" else "B") + sig[1:]])
    with pytest.raises(security.TokenInvalid):
        security.decode_access_token(tampered)
    with pytest.raises(security.TokenInvalid):
        security.decode_access_token("garbage")


def test_refresh_token_is_random_and_hashed() -> None:
    a, b = security.new_refresh_token(), security.new_refresh_token()
    assert a != b and len(a) >= 43
    h = security.hash_refresh_token(a)
    assert len(h) == 64 and h == security.hash_refresh_token(a) and a not in h
