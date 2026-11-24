"""Private storage of card images (specs/005 research.md R6, R7).

Files live in UPLOADS_DIR (the `uploads` Docker volume, outside any web root) as
`<uuid4 hex>.jpg`. They are reachable only through the permission-checked API route.
Log lines carry file names only, never card data (Principle II).
"""

import io
import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import get_settings
from app.errors import AppError
from app.models.draft import MAX_IMAGE_EDGE

log = logging.getLogger("sijil.images")

JPEG_MAGIC = b"\xff\xd8\xff"
CHUNK = 64 * 1024
_NAME = re.compile(r"[0-9a-f]{32}\.jpg")
TEMP_SUFFIX = ".part"

# Pillow refuses decompression bombs above this many pixels; ours are at most 1600×1600.
Image.MAX_IMAGE_PIXELS = 4 * MAX_IMAGE_EDGE * MAX_IMAGE_EDGE


@dataclass(frozen=True)
class StoredImage:
    file_name: str
    size_bytes: int
    width: int
    height: int


def uploads_dir() -> Path:
    return Path(get_settings().uploads_dir)


def open_path(file_name: str) -> Path:
    """Absolute path of a stored file. Only names we generated are accepted (no traversal)."""
    if not _NAME.fullmatch(file_name):
        raise AppError("image_not_found", 404)
    return uploads_dir() / file_name


def _read_capped(upload: UploadFile, limit: int) -> bytes:
    buf = bytearray()
    while chunk := upload.file.read(CHUNK):
        buf.extend(chunk)
        if len(buf) > limit:
            raise AppError("image_too_large", 413)
    return bytes(buf)


def _verify(data: bytes) -> tuple[int, int]:
    if not data.startswith(JPEG_MAGIC):
        raise AppError("invalid_image", 422)
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "JPEG":
                raise AppError("invalid_image", 422)
            image.load()
            width, height = image.size
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise AppError("invalid_image", 422) from None
    if max(width, height) > MAX_IMAGE_EDGE:
        raise AppError("image_too_big_dimensions", 422)
    return width, height


def save_upload(upload: UploadFile) -> StoredImage:
    """Check and store an uploaded card image; nothing is written if any check fails."""
    data = _read_capped(upload, get_settings().max_image_bytes)
    width, height = _verify(data)

    directory = uploads_dir()
    file_name = f"{uuid.uuid4().hex}.jpg"
    final = directory / file_name
    temp = directory / f"{file_name}{TEMP_SUFFIX}"
    try:
        with open(temp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, final)
    except OSError:
        unlink_quietly(temp.name)
        log.error("could not store image %s", file_name)
        raise
    return StoredImage(file_name=file_name, size_bytes=len(data), width=width, height=height)


LEGACY_JPEG_QUALITY = 80
_DECODABLE = ("JPEG", "PNG")


def _reencode(data: bytes) -> tuple[bytes, int, int]:
    """JPEG or PNG → upright RGB JPEG, ≤ MAX_IMAGE_EDGE on the long edge, without metadata."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in _DECODABLE:
                raise AppError("invalid_image", 422)
            probe.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            upright = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise AppError("invalid_image", 422) from None
    upright.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
    out = io.BytesIO()
    upright.save(out, format="JPEG", quality=LEGACY_JPEG_QUALITY)
    return out.getvalue(), upright.width, upright.height


def save_bytes(data: bytes) -> StoredImage:
    """Store an image fetched by the server (specs/014 legacy images, research R7): re-encoded to
    the limits of phone uploads. Nothing is written if the bytes are not a JPEG or PNG image."""
    jpeg, width, height = _reencode(data)
    file_name = f"{uuid.uuid4().hex}.jpg"
    _write_atomic(file_name, jpeg)
    return StoredImage(file_name=file_name, size_bytes=len(jpeg), width=width, height=height)


def _write_atomic(file_name: str, data: bytes) -> None:
    directory = uploads_dir()
    temp = directory / f"{file_name}{TEMP_SUFFIX}"
    try:
        with open(temp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, directory / file_name)
    except OSError:
        unlink_quietly(temp.name)
        log.error("could not store image %s", file_name)
        raise


def unlink_quietly(file_name: str) -> None:
    """Remove a stored (or temporary) file; a failure is logged by name only."""
    try:
        (uploads_dir() / Path(file_name).name).unlink(missing_ok=True)
    except OSError:
        log.warning("could not remove image file %s", file_name)


def prune_orphans(referenced: set[str], older_than: timedelta = timedelta(hours=1)) -> list[str]:
    """Delete files no row refers to and older than `older_than` (research.md R8).

    Covers a crash between commit and unlink, and uploads abandoned mid-write. Returns the
    removed names.
    """
    cutoff = datetime.now(UTC) - older_than
    removed: list[str] = []
    for path in uploads_dir().iterdir():
        if not path.is_file() or path.name in referenced:
            continue
        if not (_NAME.fullmatch(path.name) or path.name.endswith(TEMP_SUFFIX)):
            continue  # never touch files this app did not create
        if datetime.fromtimestamp(path.stat().st_mtime, UTC) >= cutoff:
            continue
        unlink_quietly(path.name)
        removed.append(path.name)
    return removed
