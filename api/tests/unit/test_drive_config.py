"""Drive fetcher settings guard (specs/014 research R7): no fake fetcher in staging/production."""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {"database_url": "postgresql://x/y", "jwt_secret": "s" * 40, "cookie_secure": True}
STRONG = {
    name: "p" * 20
    for name in ("postgres_password", "superadmin_password", "demo_marketer_password")
}


@pytest.mark.parametrize("env", ["staging", "production"])
def test_fake_drive_refused_in_strict_envs(env) -> None:
    with pytest.raises(ValidationError, match="DRIVE_MODE must be google"):
        Settings(**BASE, **STRONG, app_env=env, otp_mode="otpiq", drive_mode="fake")


def test_google_is_the_default_and_fake_is_allowed_in_dev(monkeypatch) -> None:
    monkeypatch.delenv("DRIVE_MODE", raising=False)  # conftest sets fake for every test
    assert Settings(**BASE, app_env="development").drive_mode == "google"
    assert Settings(**BASE, app_env="test", drive_mode="fake").drive_mode == "fake"
    assert Settings(**BASE, **STRONG, app_env="production", otp_mode="otpiq").drive_mode == "google"
