"""Application settings, read from environment variables (.env). See .env.example."""

import re
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRET = "change-me"  # noqa: S105 - the placeholder value we refuse in staging/production

# An age X25519 public key: "age1" + 58 bech32 characters (specs/016 research R2).
_AGE_RECIPIENT = re.compile(r"age1[02-9ac-hj-np-z]{58}")
_HH_MM = re.compile(r"([01]?[0-9]|2[0-3]):([0-5][0-9])")


class Settings(BaseSettings):
    # hide_input_in_errors: a refused setting never echoes its value (secrets, specs/016 T003).
    model_config = SettingsConfigDict(
        env_file=None, extra="ignore", case_sensitive=False, hide_input_in_errors=True
    )

    app_env: Literal["development", "test", "staging", "production"] = "production"

    database_url: str
    test_database_url: str | None = None
    postgres_password: str | None = None

    jwt_secret: str
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = True

    lockout_threshold: int = 5
    lockout_minutes: int = 15
    login_ip_limit: int = 20
    login_ip_window_minutes: int = 15

    superadmin_phone: str | None = None
    superadmin_name: str | None = None
    superadmin_password: str | None = None
    demo_marketer_password: str | None = None

    trusted_proxy_cidrs: str = "127.0.0.1"

    # Card images (specs/005 research.md R6, R7). Private storage, never under the web root.
    uploads_dir: str = "/data/uploads"
    max_image_bytes: int = 5 * 1024 * 1024
    # Export files (specs/019 research.md R10): the `exports` volume, mounted on `api` only and
    # never backed up. A file is removed 24 h after it is ready.
    exports_dir: str = "/data/exports"

    # Google Maps (specs/005 research.md R10). Empty key → the form works without the map.
    google_maps_api_key: str = ""
    google_maps_map_id: str = ""
    map_default_center: str = "33.3152,44.3661"

    # Card reader (specs/006 research.md R3, R10). `fake` = synthetic results, no models (tests,
    # e2e); `http` = the internal `ocr` service. The source URL is the public copy of ocr/ (R12).
    ocr_mode: Literal["http", "fake"] = "http"
    ocr_url: str = "http://ocr:8080"
    ocr_source_url: str = ""

    # Phone OTP (specs/007 research.md R1, R8). `otpiq` = the OTPIQ WhatsApp API; `fake` = an
    # in-memory sender for tests and e2e. `otp_fake_code` fixes the code (fake mode only), so e2e
    # knows it without any endpoint or log revealing a code. Both are refused in staging/production.
    otp_mode: Literal["otpiq", "fake"] = "otpiq"
    otpiq_api_key: str = ""
    otpiq_base_url: str = "https://api.otpiq.com/api"
    otp_fake_code: str = ""

    # Legacy card images (specs/014 research R7). `google` = download shared Google Drive links;
    # `fake` = generated images and failures by file id (tests, e2e, local development). `fake`
    # is refused in staging/production.
    drive_mode: Literal["google", "fake"] = "google"

    # Backups (specs/016 research R2, R5, R6; contracts/cli.md). Read by the `backup` service; the
    # app containers never mount `backup_dir`. The recipient is the public key only: the server can
    # encrypt but never decrypt. `backup_external_dir` is shown read-only on the backup page.
    backup_dir: str = "/data/backups"
    backup_age_recipient: str = ""
    backup_nightly_at: str = "03:00"
    backup_min_free_gb: int = Field(default=2, gt=0)
    backup_external_dir: str = ""

    @property
    def backup_nightly_minutes(self) -> int:
        """`backup_nightly_at` as minutes after Baghdad midnight."""
        hours, minutes = self.backup_nightly_at.split(":")
        return int(hours) * 60 + int(minutes)

    @property
    def map_center(self) -> tuple[float, float]:
        """`map_default_center` as (lat, lng); validated at startup by `_check_map_center`."""
        lat, lng = (float(part) for part in self.map_default_center.split(","))
        return lat, lng

    @model_validator(mode="after")
    def _check_map_center(self) -> "Settings":
        try:
            parts = self.map_default_center.split(",")
            if len(parts) != 2:
                raise ValueError
            lat, lng = float(parts[0]), float(parts[1])
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError
        except ValueError:
            raise ValueError(
                'MAP_DEFAULT_CENTER must be "lat,lng" with valid coordinates'
            ) from None
        if self.max_image_bytes <= 0:
            raise ValueError("MAX_IMAGE_BYTES must be a positive number of bytes")
        if self.otp_fake_code:
            if self.otp_mode != "fake":
                raise ValueError("OTP_FAKE_CODE is allowed only with OTP_MODE=fake")
            if not (
                len(self.otp_fake_code) == 6
                and self.otp_fake_code.isascii()
                and self.otp_fake_code.isdigit()
            ):
                raise ValueError("OTP_FAKE_CODE must be exactly 6 digits")
        if self.backup_age_recipient and not _AGE_RECIPIENT.fullmatch(self.backup_age_recipient):
            # Never the value: a secret key pasted by mistake must not reach a log.
            raise ValueError("BACKUP_AGE_RECIPIENT must be an age public key (age1…)")
        if not (self.backup_nightly_at.isascii() and _HH_MM.fullmatch(self.backup_nightly_at)):
            raise ValueError('BACKUP_NIGHTLY_AT must be "HH:MM" (Baghdad time)')
        return self

    @property
    def is_strict(self) -> bool:
        """staging behaves like production for secrets and cookies."""
        return self.app_env in ("staging", "production")

    @model_validator(mode="after")
    def _refuse_weak_config(self) -> "Settings":
        if not self.is_strict:
            return self
        problems: list[str] = []
        if self.jwt_secret == PLACEHOLDER_SECRET or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be a random value of at least 32 characters")
        for name in ("postgres_password", "superadmin_password", "demo_marketer_password"):
            if getattr(self, name) == PLACEHOLDER_SECRET:
                problems.append(f"{name.upper()} must not be the placeholder value")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true")
        if self.otp_mode == "fake":
            problems.append("OTP_MODE must be otpiq")
        if self.otp_fake_code:
            problems.append("OTP_FAKE_CODE must be empty")
        if self.drive_mode == "fake":
            problems.append("DRIVE_MODE must be google")
        if problems:
            # Names only — never the values.
            raise ValueError(f"Refusing to start in {self.app_env}: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
