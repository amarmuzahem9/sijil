"""Application settings, read from environment variables (.env). See .env.example."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRET = "change-me"  # noqa: S105 - the placeholder value we refuse in staging/production


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

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

    # Google Maps (specs/005 research.md R10). Empty key → the form works without the map.
    google_maps_api_key: str = ""
    google_maps_map_id: str = ""
    map_default_center: str = "33.3152,44.3661"

    # Card reader (specs/006 research.md R3, R10). `fake` = synthetic results, no models (tests,
    # e2e); `http` = the internal `ocr` service. The source URL is the public copy of ocr/ (R12).
    ocr_mode: Literal["http", "fake"] = "http"
    ocr_url: str = "http://ocr:8080"
    ocr_source_url: str = ""

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
        if problems:
            # Names only — never the values.
            raise ValueError(f"Refusing to start in {self.app_env}: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
