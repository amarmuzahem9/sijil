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


def _encoded(fmt: str, size: tuple[int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("L", size, 128).save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize("fmt", ["PNG", "JPEG"])
def test_images_above_the_legacy_pixel_limit_are_refused(uploads, monkeypatch, fmt) -> None:
    monkeypatch.setattr(image_store, "LEGACY_MAX_PIXELS", 1000)
    with pytest.raises(AppError) as err:
        image_store.save_bytes(_encoded(fmt, (100, 100)))  # 10 000 px > 1000
    assert err.value.code == "invalid_image"
    assert list(uploads.iterdir()) == []


def test_legacy_limit_is_120_megapixels_and_separate_from_uploads() -> None:
    assert image_store.LEGACY_MAX_PIXELS == 120_000_000
    # The phone upload guard is untouched (system.md §5.1 sizes; batch 2 decision).
    assert Image.MAX_IMAGE_PIXELS == 4 * 1600 * 1600


def test_a_30_megapixel_photo_is_stored_reduced_and_the_upload_guard_stays(uploads) -> None:
    """Above the upload guard (about 20 MP), below the legacy limit: accepted for Drive images."""
    stored = image_store.save_bytes(_encoded("JPEG", (6000, 5000)))
    assert max(stored.width, stored.height) == 1600
    assert Image.MAX_IMAGE_PIXELS == 4 * 1600 * 1600


def test_the_phone_upload_path_still_refuses_30_megapixels() -> None:
    with pytest.raises(AppError):
        image_store._verify(_encoded("JPEG", (6000, 5000)))
