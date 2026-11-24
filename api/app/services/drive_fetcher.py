"""Google Drive download adapter for the legacy card images (specs/014 research R7; constitution
Principle VII: a swappable adapter with a fake).

`google` downloads `https://drive.google.com/uc?export=download&id=<id>`; the file must be shared
«لأي شخص لديه الرابط». An HTML answer is Drive's sign-in or permission page, so the file is not
shared. `fake` answers by id prefix with generated images or failures, for tests, e2e and local
development; it is refused in staging/production (config). File ids and bytes are never logged.
"""

import hashlib
import io
import logging
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from PIL import Image, ImageDraw

from app.config import get_settings

log = logging.getLogger("sijil.drive")

Outcome = Literal["ok", "not_shared", "not_found", "too_large", "not_image", "timeout", "network"]
MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024
TIMEOUT_SECONDS = 30.0
DOWNLOAD_URL = "https://drive.google.com/uc"


@dataclass(frozen=True)
class FetchResult:
    outcome: Outcome
    data: bytes | None = None


class Fetcher(Protocol):
    def fetch(self, file_id: str) -> FetchResult: ...


class GoogleFetcher:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=TIMEOUT_SECONDS)

    def fetch(self, file_id: str) -> FetchResult:
        try:
            with self._client.stream(
                "GET",
                DOWNLOAD_URL,
                params={"export": "download", "id": file_id},
                follow_redirects=True,
                timeout=TIMEOUT_SECONDS,
            ) as response:
                if response.status_code in (401, 403):
                    return FetchResult("not_shared")
                if response.status_code == 404:
                    return FetchResult("not_found")
                if response.status_code != 200:
                    log.warning("drive download failed status=%s", response.status_code)
                    return FetchResult("network")
                if "text/html" in response.headers.get("content-type", "").lower():
                    return FetchResult("not_shared")
                length = response.headers.get("content-length")
                if length and length.isdigit() and int(length) > MAX_DOWNLOAD_BYTES:
                    return FetchResult("too_large")
                buf = bytearray()
                for chunk in response.iter_bytes():
                    buf.extend(chunk)
                    if len(buf) > MAX_DOWNLOAD_BYTES:
                        return FetchResult("too_large")
                return FetchResult("ok", bytes(buf))
        except httpx.TimeoutException:
            return FetchResult("timeout")
        except httpx.HTTPError:
            log.warning("drive download failed: network")
            return FetchResult("network")


def _generated(file_id: str, fmt: str) -> bytes:
    """A synthetic card-sized picture, coloured by the id (never a real card)."""
    digest = hashlib.sha256(file_id.encode()).digest()
    img = Image.new("RGB", (1000, 630), tuple(digest[:3]))
    draw = ImageDraw.Draw(img)
    draw.rectangle((40, 40, 960, 590), outline=(255, 255, 255), width=8)
    draw.text((80, 80), f"SYNTHETIC {file_id}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class FakeFetcher:
    _FAILURES: dict[str, Outcome] = {
        "fake-private-": "not_shared",
        "fake-missing-": "not_found",
        "fake-big-": "too_large",
        "fake-timeout-": "timeout",
    }

    def fetch(self, file_id: str) -> FetchResult:
        if file_id.startswith("fake-ok-"):
            return FetchResult("ok", _generated(file_id, "JPEG"))
        if file_id.startswith("fake-png-"):
            return FetchResult("ok", _generated(file_id, "PNG"))
        if file_id.startswith("fake-text-"):
            return FetchResult("ok", b"this is not an image " + file_id.encode())
        for prefix, outcome in self._FAILURES.items():
            if file_id.startswith(prefix):
                return FetchResult(outcome)
        return FetchResult("not_found")


def get_fetcher() -> Fetcher:
    return FakeFetcher() if get_settings().drive_mode == "fake" else GoogleFetcher()
