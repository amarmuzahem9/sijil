"""The Google Drive adapter (specs/014 research R7): google over httpx, and the fake.

No test reaches the network: the google adapter runs on httpx.MockTransport.
"""

import io

import httpx
import pytest
from PIL import Image

from app.services import drive_fetcher as df


def _image_format(data: bytes) -> str:
    with Image.open(io.BytesIO(data)) as img:
        return img.format


# --- fake ---


def test_fake_ok_gives_a_jpeg_and_png_gives_a_png() -> None:
    fake = df.FakeFetcher()
    ok = fake.fetch("fake-ok-front-01")
    assert ok.outcome == "ok"
    assert _image_format(ok.data) == "JPEG"
    png = fake.fetch("fake-png-front-01")
    assert png.outcome == "ok"
    assert _image_format(png.data) == "PNG"


def test_fake_images_differ_by_id() -> None:
    fake = df.FakeFetcher()
    assert fake.fetch("fake-ok-a-000001").data != fake.fetch("fake-ok-b-000001").data


@pytest.mark.parametrize(
    ("file_id", "outcome"),
    [
        ("fake-private-0001", "not_shared"),
        ("fake-missing-0001", "not_found"),
        ("fake-big-00000001", "too_large"),
        ("fake-timeout-0001", "timeout"),
        ("1AbC_dEf-GhIjKlMn", "not_found"),  # the fake never pretends a real id exists
    ],
)
def test_fake_failures(file_id, outcome) -> None:
    result = df.FakeFetcher().fetch(file_id)
    assert result.outcome == outcome
    assert result.data is None


def test_fake_text_returns_bytes_that_are_not_an_image() -> None:
    result = df.FakeFetcher().fetch("fake-text-000001")
    assert result.outcome == "ok"
    with pytest.raises(Exception):  # noqa: B017 — any Pillow refusal
        Image.open(io.BytesIO(result.data)).verify()


def test_get_fetcher_follows_drive_mode(monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.setenv("DRIVE_MODE", "fake")
    get_settings.cache_clear()
    try:
        assert isinstance(df.get_fetcher(), df.FakeFetcher)
        monkeypatch.setenv("DRIVE_MODE", "google")
        get_settings.cache_clear()
        assert isinstance(df.get_fetcher(), df.GoogleFetcher)
    finally:
        monkeypatch.setenv("DRIVE_MODE", "fake")
        get_settings.cache_clear()


# --- google over a mock transport ---

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


def _google(handler) -> df.GoogleFetcher:
    return df.GoogleFetcher(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_google_asks_the_download_url_and_returns_the_bytes() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})

    result = _google(handler).fetch("1AbC_dEf-GhIjKlMn")
    assert result == df.FetchResult("ok", JPEG)
    assert seen[0].host == "drive.google.com"
    assert seen[0].params["id"] == "1AbC_dEf-GhIjKlMn"
    assert seen[0].params["export"] == "download"


def test_google_follows_the_redirect_to_the_content_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "drive.google.com":
            return httpx.Response(
                303, headers={"location": "https://drive.usercontent.google.com/download?id=x"}
            )
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})

    assert _google(handler).fetch("1AbC_dEf-GhIjKlMn").outcome == "ok"


@pytest.mark.parametrize(
    ("response", "outcome"),
    [
        (
            httpx.Response(
                200, content=b"<html>sign in</html>", headers={"content-type": "text/html"}
            ),
            "not_shared",
        ),
        (httpx.Response(403), "not_shared"),
        (httpx.Response(401), "not_shared"),
        (httpx.Response(404), "not_found"),
        (httpx.Response(500), "network"),
        (
            httpx.Response(
                200,
                content=b"x",
                headers={"content-type": "image/jpeg", "content-length": str(16 * 1024 * 1024)},
            ),
            "too_large",
        ),
    ],
)
def test_google_status_mapping(response, outcome) -> None:
    result = _google(lambda request: response).fetch("1AbC_dEf-GhIjKlMn")
    assert result.outcome == outcome
    assert result.data is None


def test_google_stops_reading_past_the_limit_without_content_length() -> None:
    chunk = b"\xff" * (1024 * 1024)

    def body():
        for _ in range(df.MAX_DOWNLOAD_BYTES // len(chunk) + 2):
            yield chunk

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body(), headers={"content-type": "image/jpeg"})

    assert _google(handler).fetch("1AbC_dEf-GhIjKlMn").outcome == "too_large"


@pytest.mark.parametrize(
    ("exc", "outcome"),
    [(httpx.ReadTimeout("slow"), "timeout"), (httpx.ConnectError("down"), "network")],
)
def test_google_transport_errors(exc, outcome) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    assert _google(handler).fetch("1AbC_dEf-GhIjKlMn").outcome == outcome
