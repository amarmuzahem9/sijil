"""Reading the legacy file (specs/014 research R4): .xlsx or .csv, in memory. Synthetic rows."""

import csv
import io
from datetime import datetime

import pytest
from openpyxl import Workbook

from app.errors import AppError
from app.services import legacy_file

HEADERS = ["طابع زمني", "الاسم الاول", "الرقم العائلي", "رقم الهاتف", "ID"]
ROWS = [
    ["2024/05/12 10:23:45", "سمير", "1234A5678901234506", "07801234567", "T3C-001"],
    ["2024/05/13 09:00:00", "علي", "1234A5678901234507", "07801234568", "T3C-002"],
]


def _csv(rows, bom: bool = False) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADERS)
    writer.writerows(rows)
    data = buf.getvalue().encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if bom else data


def _xlsx(rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.parametrize("bom", [False, True])
def test_csv_rows(bom) -> None:
    headers, rows = legacy_file.read_table(_csv(ROWS, bom=bom))
    assert headers == HEADERS
    assert rows == ROWS


def test_xlsx_gives_the_same_rows() -> None:
    headers, rows = legacy_file.read_table(_xlsx(ROWS))
    assert headers == HEADERS
    assert rows == ROWS


def test_xlsx_keeps_date_cells_as_datetimes() -> None:
    stamp = datetime(2024, 5, 12, 10, 23, 45)
    _, rows = legacy_file.read_table(_xlsx([[stamp, "سمير", "X", "07801234567", "T3C-001"]]))
    assert rows[0][0] == stamp


def test_empty_rows_are_ignored_and_short_rows_padded() -> None:
    _, rows = legacy_file.read_table(_csv([ROWS[0], ["", "", "", "", ""], ["", "علي"]]))
    assert rows == [ROWS[0], [None, "علي", None, None, None]]


@pytest.mark.parametrize(
    "data",
    [
        b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n\x00\x01binary",
        b"PK\x03\x04broken zip",
        "طابع زمني,ID".encode("utf-16"),
        b"",
        b"\n\n",
    ],
)
def test_unreadable_files_are_refused(data) -> None:
    with pytest.raises(AppError) as err:
        legacy_file.read_table(data)
    assert err.value.code == "import_file_unreadable"


def test_too_many_rows_refused() -> None:
    rows = [["", "اسم", "X", "", f"T3C-{i % 999 + 1:03d}"] for i in range(2001)]
    with pytest.raises(AppError) as err:
        legacy_file.read_table(_csv(rows))
    assert err.value.code == "import_too_many_rows"


def test_too_large_refused() -> None:
    with pytest.raises(AppError) as err:
        legacy_file.read_table(b"a" * (legacy_file.MAX_FILE_BYTES + 1))
    assert err.value.code == "import_file_too_large"
    assert err.value.status == 413
