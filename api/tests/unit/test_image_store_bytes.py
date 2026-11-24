"""image_store.save_bytes (specs/014 research R7): legacy images stored like phone uploads —
JPEG, at most 1600 px on the long edge, upright, without metadata. Generated images only."""

import io
from pathlib import Path

import pytest
from PIL import Image

from app.config import get_settings
from app.errors import AppError
from app.services import image_store


@pytest.fixture
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


def _png_rotated(width: int, height: int) -> bytes:
    """A landscape PNG whose EXIF says «rotate 90°» (orientation 6)."""
    img = Image.new("RGB", (width, height), (200, 30, 30))
    exif = Image.Exif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    img.save(buf, format="PNG", exif=exif)
    return buf.getvalue()


def test_large_png_becomes_an_upright_jpeg_within_1600_without_exif(uploads) -> None:
    stored = image_store.save_bytes(_png_rotated(3000, 2000))
    path = uploads / stored.file_name
    with Image.open(path) as img:
        assert img.format == "JPEG"
        assert img.size == (1067, 1600)  # rotated to portrait, long edge 1600
        assert not img.getexif()
    assert (stored.width, stored.height) == (1067, 1600)
    assert stored.size_bytes == path.stat().st_size
    assert image_store.open_path(stored.file_name) == path


def test_small_jpeg_keeps_its_size(uploads) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (800, 500), (10, 10, 10)).save(buf, format="JPEG")
    stored = image_store.save_bytes(buf.getvalue())
    assert (stored.width, stored.height) == (800, 500)


@pytest.mark.parametrize("data", [b"hello, not an image", b"GIF89a" + b"\x00" * 50, b""])
def test_non_images_are_refused_and_nothing_is_written(uploads, data) -> None:
    with pytest.raises(AppError) as err:
        image_store.save_bytes(data)
    assert err.value.code == "invalid_image"
    assert list(uploads.iterdir()) == []


def test_gif_is_refused(uploads) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (50, 50)).save(buf, format="GIF")
    with pytest.raises(AppError):
        image_store.save_bytes(buf.getvalue())
    assert list(uploads.iterdir()) == []


def test_decompression_bomb_is_refused(uploads, monkeypatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    buf = io.BytesIO()
    Image.new("L", (100, 100)).save(buf, format="PNG")  # 10 000 px > 2 × 1000
    with pytest.raises(AppError) as err:
        image_store.save_bytes(buf.getvalue())
    assert err.value.code == "invalid_image"
    assert list(uploads.iterdir()) == []
