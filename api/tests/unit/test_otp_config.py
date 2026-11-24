"""OTP settings guard (specs/007 research.md R8): no fake sender in staging or production."""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {"database_url": "postgresql://x/y", "jwt_secret": "s" * 40, "cookie_secure": True}


@pytest.mark.parametrize("env", ["staging", "production"])
def test_fake_mode_refused_in_strict_envs(env) -> None:
    with pytest.raises(ValidationError, match="OTP_MODE must be otpiq"):
        Settings(**BASE, app_env=env, otp_mode="fake")


def test_fake_code_needs_fake_mode() -> None:
    with pytest.raises(ValidationError, match="OTP_FAKE_CODE is allowed only"):
        Settings(**BASE, app_env="development", otp_mode="otpiq", otp_fake_code="246810")


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "١٢٣٤٥٦"])
def test_fake_code_must_be_six_ascii_digits(code) -> None:
    with pytest.raises(ValidationError, match="exactly 6 digits"):
        Settings(**BASE, app_env="development", otp_mode="fake", otp_fake_code=code)


def test_dev_fake_with_code_and_production_otpiq_are_accepted() -> None:
    assert Settings(**BASE, app_env="test", otp_mode="fake", otp_fake_code="246810").otp_fake_code
    strong = {
        name: "p" * 20
        for name in ("postgres_password", "superadmin_password", "demo_marketer_password")
    }
    # drive_mode explicit: conftest sets DRIVE_MODE=fake, which production refuses (specs/014).
    production = Settings(
        **BASE, **strong, app_env="production", otp_mode="otpiq", drive_mode="google"
    )
    assert production.otp_mode == "otpiq"
