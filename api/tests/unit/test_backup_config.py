"""Backup settings (specs/016 research R5, R6, contracts/cli.md «.env additions», task T003)."""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {"database_url": "postgresql://x/y", "jwt_secret": "s" * 40, "cookie_secure": True}
# A syntactically valid, synthetic recipient (not a key anyone holds).
RECIPIENT = "age1" + "q" * 58


def test_defaults(monkeypatch) -> None:
    # The container's own .env may set them (a local key); the defaults are what we check here.
    for name in (
        "BACKUP_DIR",
        "BACKUP_AGE_RECIPIENT",
        "BACKUP_NIGHTLY_AT",
        "BACKUP_MIN_FREE_GB",
        "BACKUP_EXTERNAL_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
    s = Settings(**BASE, app_env="test")
    assert s.backup_dir == "/data/backups"
    assert s.backup_age_recipient == ""
    assert s.backup_nightly_at == "03:00"
    assert s.backup_min_free_gb == 2
    assert s.backup_external_dir == ""


def test_recipient_accepted_when_it_is_an_age_public_key() -> None:
    assert Settings(**BASE, app_env="test", backup_age_recipient=RECIPIENT).backup_age_recipient


@pytest.mark.parametrize(
    "value", ["age1", "AGE-SECRET-KEY-1" + "Q" * 58, "ssh-ed25519 AAAA", "age1 " + "q" * 58]
)
def test_recipient_refused_when_not_a_public_key(value) -> None:
    # A secret key pasted by mistake must never be accepted (the server holds the public key only).
    with pytest.raises(ValidationError, match="BACKUP_AGE_RECIPIENT"):
        Settings(**BASE, app_env="test", backup_age_recipient=value)


def test_refusal_message_never_echoes_the_value() -> None:
    secret = "AGE-SECRET-KEY-1" + "Z" * 58
    with pytest.raises(ValidationError) as info:
        Settings(**BASE, app_env="test", backup_age_recipient=secret)
    assert secret not in str(info.value)


@pytest.mark.parametrize("value", ["03:00", "00:00", "23:59", "4:30"])
def test_nightly_time_accepted(value) -> None:
    assert Settings(**BASE, app_env="test", backup_nightly_at=value).backup_nightly_at == value


@pytest.mark.parametrize("value", ["24:00", "3", "03:60", "٠٣:٠٠", "03:00:00", ""])
def test_nightly_time_refused(value) -> None:
    with pytest.raises(ValidationError, match="BACKUP_NIGHTLY_AT"):
        Settings(**BASE, app_env="test", backup_nightly_at=value)


@pytest.mark.parametrize("value", [0, -1])
def test_min_free_must_be_positive(value) -> None:
    with pytest.raises(ValidationError):
        Settings(**BASE, app_env="test", backup_min_free_gb=value)


def test_nightly_minutes() -> None:
    assert Settings(**BASE, app_env="test", backup_nightly_at="4:30").backup_nightly_minutes == 270
