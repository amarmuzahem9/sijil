"""Reader service checks inside the `ocr` image (tasks T005). Synthetic images only.

Run: docker compose run --rm --network none ocr pytest -q tests
"""

import io
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from service import reader
from service.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        deadline = time.monotonic() + 120
        while c.get("/health").status_code != 200:
            assert time.monotonic() < deadline, "models did not load"
            time.sleep(0.5)
        yield c


def _blank_jpeg(width: int = 800, height: int = 500) -> bytes:
    image = np.full((height, width, 3), 235, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def test_health_reports_loaded_models(client) -> None:
    body = client.get("/health").json()
    assert body == {"status": "ok", "models": "loaded", "upstream": reader.UPSTREAM_COMMIT}


def test_blank_photo_has_no_detections(client) -> None:
    res = client.post(
        "/read",
        files={"image": ("blank.jpg", io.BytesIO(_blank_jpeg()), "image/jpeg")},
        data={"side": "front"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["detections"] == []
    assert isinstance(body["duration_ms"], int)


def test_undecodable_image_is_400(client) -> None:
    res = client.post(
        "/read",
        files={"image": ("x.jpg", io.BytesIO(b"not an image"), "image/jpeg")},
        data={"side": "back"},
    )
    assert res.status_code == 400
    assert res.json() == {"code": "bad_image"}


def test_bad_side_is_422(client) -> None:
    res = client.post(
        "/read",
        files={"image": ("blank.jpg", io.BytesIO(_blank_jpeg()), "image/jpeg")},
        data={"side": "middle"},
    )
    assert res.status_code == 422


def test_composite_check_from_raw_lines() -> None:
    # A synthetic TD1 MRZ (made-up numbers) whose check digits are all correct.
    l1 = "IDIRQA123456782199912345678<<<"
    body = "9901014M3001014IRQ<<<<<<<<<<<"
    digit = reader._check_digit(l1[5:30] + body[0:7] + body[8:15] + body[18:29])
    l2 = body + digit
    l3 = "<<TEST<<<<<<<<<<<<<<<<<<<<<<<<"
    assert reader.composite_from_raw("\n".join((l1, l2, l3))) is True
    wrong = str((int(digit) + 1) % 10)
    assert reader.composite_from_raw("\n".join((l1, body + wrong, l3))) is False
    assert reader.composite_from_raw(None) is None
    # OCR dropped two `<` fillers from the middle of line 2: still verifiable, still correct.
    short = body[:18] + body[20:] + digit
    assert len(short) == 28
    assert reader.composite_from_raw("\n".join((l1, short, l3))) is True
    assert reader.composite_from_raw("\n".join((l1, body[:18] + body[20:] + wrong, l3))) is False
