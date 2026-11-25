"""Read the legacy Google Form export (specs/014 research R4): `.xlsx` or `.csv`, in memory.

The upload is never written to disk. An `.xlsx` is recognised by its zip signature and read with
openpyxl (read-only, values only; defusedxml, installed alongside, guards its XML parser);
anything else must be UTF-8 CSV. Returns the header row and the data rows, empty rows dropped and
short rows padded to the header width. Cell values are never logged.
"""

import csv
import io
import zipfile
from typing import Any

from app.errors import AppError

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 2000
# The SAS export is larger (specs/015 research R2).
SAS_MAX_FILE_BYTES = 15 * 1024 * 1024
SAS_MAX_ROWS = 50_000
_ZIP = b"PK\x03\x04"


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _xlsx_rows(data: bytes) -> list[list[Any]]:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise AppError("import_file_unreadable", 422) from exc
    try:
        sheet = workbook.worksheets[0]
        return [list(row) for row in sheet.iter_rows(values_only=True)]
    except Exception as exc:  # noqa: BLE001 — any broken workbook is «unreadable»
        raise AppError("import_file_unreadable", 422) from exc
    finally:
        workbook.close()


def _csv_rows(data: bytes) -> list[list[Any]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError("import_file_unreadable", 422) from exc
    if "\x00" in text:
        raise AppError("import_file_unreadable", 422)
    try:
        return [list(row) for row in csv.reader(io.StringIO(text, newline=""))]
    except csv.Error as exc:
        raise AppError("import_file_unreadable", 422) from exc


def too_large(max_bytes: int) -> AppError:
    return AppError(
        "import_file_too_large",
        413,
        message=f"حجم الملف أكبر من {max_bytes // (1024 * 1024)} ميغابايت",
    )


def read_table(
    data: bytes, *, max_bytes: int = MAX_FILE_BYTES, max_rows: int = MAX_ROWS
) -> tuple[list[Any], list[list[Any]]]:
    """(headers, rows). Raises `import_file_too_large`, `import_file_unreadable`,
    `import_too_many_rows`; the messages name the given limits."""
    if len(data) > max_bytes:
        raise too_large(max_bytes)
    raw = _xlsx_rows(data) if data.startswith(_ZIP) else _csv_rows(data)
    rows = [
        [None if _blank(cell) else cell for cell in row]
        for row in raw
        if not all(_blank(cell) for cell in row)
    ]
    if not rows:
        raise AppError("import_file_unreadable", 422)
    headers, body = rows[0], rows[1:]
    if len(body) > max_rows:
        raise AppError("import_too_many_rows", 422, message=f"الملف فيه أكثر من {max_rows:,} صف")
    width = len(headers)
    body = [(row + [None] * width)[:width] if len(row) < width else row for row in body]
    return headers, body
