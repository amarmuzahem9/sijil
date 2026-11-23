"""OTP rules (specs/007 research.md R3, R4; data-model.md › Validation rules)."""

import re
import uuid

import pytest

from app.core import otp

PHONE = "07801234567"


def _ctx(**overrides):
    values = {
        "phone": PHONE,
        "tower_id": 3,
        "plan_id": 7,
        "trial_price": 20000,
        "second_price": 35000,
    }
    values.update(overrides)
    return otp.context_hash(**values)


def test_generate_code_is_six_ascii_digits() -> None:
    for _ in range(200):
        code = otp.generate_code()
        assert re.fullmatch(r"[0-9]{6}", code)


def test_generate_code_uses_fixed_code_when_given() -> None:
    assert otp.generate_code(fixed="246810") == "246810"


def test_code_hash_is_deterministic_and_bound_to_challenge() -> None:
    cid = uuid.uuid4()
    first = otp.code_hash(cid, "123456")
    assert first == otp.code_hash(cid, "123456")
    assert first != otp.code_hash(uuid.uuid4(), "123456")
    assert first != otp.code_hash(cid, "123457")
    assert "123456" not in first
    assert re.fullmatch(r"[0-9a-f]{64}", first)


def test_verify_code_hash_accepts_only_the_right_code() -> None:
    cid = uuid.uuid4()
    stored = otp.code_hash(cid, "000042")
    assert otp.verify_code_hash(cid, "000042", stored)
    assert not otp.verify_code_hash(cid, "000043", stored)
    assert not otp.verify_code_hash(uuid.uuid4(), "000042", stored)


def test_context_hash_is_stable_for_equal_values() -> None:
    assert _ctx() == _ctx()
    assert re.fullmatch(r"[0-9a-f]{64}", _ctx())


@pytest.mark.parametrize(
    "field,value",
    [
        ("phone", "07801234568"),
        ("tower_id", 4),
        ("plan_id", 8),
        ("trial_price", 25000),
        ("second_price", 30000),
    ],
)
def test_context_hash_changes_with_each_field(field, value) -> None:
    assert _ctx(**{field: value}) != _ctx()


def test_context_hash_treats_none_as_empty_and_distinct_from_values() -> None:
    assert _ctx(tower_id=None) == _ctx(tower_id=None)
    assert _ctx(tower_id=None) != _ctx()
    # Field boundaries are kept: moving a digit between fields changes the hash.
    assert _ctx(tower_id=12, plan_id=3) != _ctx(tower_id=1, plan_id=23)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("123456", "123456"),
        ("١٢٣ ٤٥٦", "123456"),
        ("۱۲۳۴۵۶", "123456"),
        (" 12 34 56 ", "123456"),
        ("12345", None),
        ("1234567", None),
        ("12345a", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_code_entry(raw, expected) -> None:
    assert otp.normalize_code_entry(raw) == expected


def test_mask_phone() -> None:
    assert otp.mask_phone("07801234567") == "0780****567"
    assert otp.mask_phone(None) == "-"
    assert otp.mask_phone("123") == "***"


def test_international_format() -> None:
    assert otp.to_international("07801234567") == "9647801234567"


def test_limits() -> None:
    assert otp.RESEND_WAIT.total_seconds() == 60
    assert otp.HOURLY_WINDOW.total_seconds() == 3600
    assert otp.HOURLY_MAX == 5
    assert otp.MAX_ATTEMPTS == 3
