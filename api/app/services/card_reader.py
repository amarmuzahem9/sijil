"""Card reader adapter (Principle VII; specs/006 research R10, contracts/ocr-service.md).

- `HttpCardReader`: the internal `ocr` service (no internet, internal network only).
- `FakeCardReader`: synthetic results without models, chosen by the photo's corner colour. Used
  by every automated test and by the e2e stack.

Both return the reader's raw answer `{duration_ms, detections}`; `card_reading_rules` decides.
Neither logs the image or any field text.
"""

import io
import logging
import math
import time
from typing import Any, Protocol

import httpx
from PIL import Image

from app.config import get_settings
from app.core.card_reading import READER_HTTP_TIMEOUT_S
from app.services import card_reader_fake_data as fake_data

log = logging.getLogger("sijil.card_reader")


class ReaderError(Exception):
    """The reader did not produce a result. `reason` is a card_readings failure reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason  # timeout | unavailable | error


class CardReader(Protocol):
    def read(self, image: bytes, side: str) -> dict[str, Any]: ...


class HttpCardReader:
    def __init__(self, base_url: str, timeout_s: float = READER_HTTP_TIMEOUT_S) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def read(self, image: bytes, side: str) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.base_url}/read",
                files={"image": ("card.jpg", image, "image/jpeg")},
                data={"side": side},
                timeout=self.timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise ReaderError("timeout") from exc
        except httpx.HTTPError as exc:
            raise ReaderError("unavailable") from exc
        if response.status_code == 503:
            raise ReaderError("unavailable")
        if response.status_code != 200:
            log.warning("reader answered HTTP %s", response.status_code)
            raise ReaderError("error")
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("detections"), list):
            raise ReaderError("error")
        return body


class FakeCardReader:
    """Synthetic reader: the top-left 32×32 colour selects a scenario (fake_data.SCENARIOS)."""

    # Seconds a "reader_slow" scenario waits; tests lower the reading limit instead.
    slow_seconds: float = 90.0

    def scenario_for(self, image: bytes, side: str) -> str:
        try:
            with Image.open(io.BytesIO(image)) as img:
                corner = img.convert("RGB").crop((0, 0, 32, 32)).resize((1, 1), Image.BOX)
                rgb = corner.getpixel((0, 0))
        except Exception:
            return fake_data.DEFAULT_FOR_SIDE[side]
        best, distance = None, math.inf
        for name, colour in fake_data.palette().items():
            d = math.dist(rgb, colour)
            if d < distance:
                best, distance = name, d
        if best is None or distance > fake_data.MAX_COLOUR_DISTANCE:
            return fake_data.DEFAULT_FOR_SIDE[side]
        return best

    def read(self, image: bytes, side: str) -> dict[str, Any]:
        scenario = fake_data.SCENARIOS[self.scenario_for(image, side)]
        if "fail" in scenario:
            raise ReaderError(scenario["fail"])
        if scenario.get("slow"):
            time.sleep(self.slow_seconds)
            raise ReaderError("timeout")
        return {"duration_ms": 5, "detections": [dict(d) for d in scenario["detections"]]}


def get_card_reader() -> CardReader:
    settings = get_settings()
    if settings.ocr_mode == "fake":
        return FakeCardReader()
    return HttpCardReader(settings.ocr_url)
