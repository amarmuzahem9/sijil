"""Pure rules for one legacy Google Form row (specs/014 research R3, R5; system.md §12.1 v1.19).

Synthetic values only.
"""

from datetime import UTC, datetime

import pytest

from app.core import legacy_row as lr

HEADERS = [
    "طابع زمني",
    "الاسم الاول",
    "الاسم الثاني",
    "الاسم الثالث",
    "اسم الام",
    "اسم اب الام",
    "تاريخ الميلاد",
    "الرقم العائلي",
    "رقم الهاتف",
    "صورة البطافة الموحدة الوجه",
    "صورة البطاقة الموحدة الظهر",
    "عنوان البريد الإلكتروني",
    "البريد الإلكتروني",
    "ID",
    "الحالة",
]


# --- headers ---


def test_headers_map_every_column() -> None:
    cols = lr.match_headers(HEADERS)
    assert cols["timestamp"] == 0
    assert cols["family_number"] == 7
    assert cols["front_image"] == 9
    assert cols["back_image"] == 10
    assert cols["email_1"] == 11
    assert cols["email_2"] == 12
    assert cols["legacy_number"] == 13
    assert cols["status"] == 14


def test_headers_tolerate_spaces_hamza_case_and_the_fixed_typo() -> None:
    headers = [f"  {h}  " for h in HEADERS]
    headers[1] = "الاسم  الأول"
    headers[9] = "صورة البطاقة الموحدة الوجه"
    headers[13] = "id"
    cols = lr.match_headers(headers)
    assert cols["first_name"] == 1
    assert cols["front_image"] == 9
    assert cols["legacy_number"] == 13


def test_missing_required_columns_are_named_in_arabic() -> None:
    headers = [h for h in HEADERS if h not in ("الرقم العائلي", "ID")]
    with pytest.raises(lr.MissingColumns) as err:
        lr.match_headers(headers)
    assert err.value.columns == ["الرقم العائلي", "ID"]


def test_optional_columns_may_be_absent() -> None:
    cols = lr.match_headers(["الاسم الاول", "الرقم العائلي", "رقم الهاتف", "ID"])
    assert "status" not in cols
    assert "front_image" not in cols


# --- single values ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("T3C-001", "T3C-001"),
        (" t3c-7 ", "T3C-007"),
        ("T3C-١٠٩", "T3C-109"),
        ("T3C 012", "T3C-012"),
        ("T3C012", "T3C-012"),
        ("ABC", None),
        ("T3C-1234", None),
        ("T3C-000", None),
        ("", None),
        (None, None),
    ],
)
def test_legacy_number(raw, expected) -> None:
    assert lr.clean_legacy_number(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  أحمد   علي ", "أحمد علي"),
        ("سمير  كاظم", "سمير كاظم"),
        ("Ali2", "Ali2"),  # historical data: kept as written (system.md 1.19 §12.1)
        ("   ", None),
        (None, None),
    ],
)
def test_name(raw, expected) -> None:
    assert lr.clean_text(raw) == expected


@pytest.mark.parametrize(
    ("raw", "phone", "flag"),
    [
        ("07801234567", "07801234567", None),
        ("‪0780 123 4567‬", "07801234567", None),
        ("+964 780 123 4567", "07801234567", None),
        (7801234567.0, "07801234567", None),  # an xlsx number lost its leading zero
        ("٠٧٨٠١٢٣٤٥٦٧", "07801234567", None),
        ("0780123", None, "phone_invalid"),
        ("", None, "phone_missing"),
        (None, None, "phone_missing"),
    ],
)
def test_phone(raw, phone, flag) -> None:
    assert lr.clean_phone(raw) == (phone, flag)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (datetime(2024, 5, 12, 10, 23, 45), datetime(2024, 5, 12, 7, 23, 45, tzinfo=UTC)),
        ("2024/05/12 10:23:45", datetime(2024, 5, 12, 7, 23, 45, tzinfo=UTC)),
        ("12/05/2024 10:23:45", datetime(2024, 5, 12, 7, 23, 45, tzinfo=UTC)),
        ("12/5/2024 10:23", datetime(2024, 5, 12, 7, 23, tzinfo=UTC)),
        ("١٢/٥/٢٠٢٤ ١٠:٢٣:٤٥ م", datetime(2024, 5, 12, 19, 23, 45, tzinfo=UTC)),
        ("12/05/2024 12:05:00 ص", datetime(2024, 5, 11, 21, 5, tzinfo=UTC)),
        ("2024-05-12", datetime(2024, 5, 11, 21, 0, tzinfo=UTC)),
        ("not a date", None),
        ("31/02/2024 10:00:00", None),
        ("", None),
        (None, None),
    ],
)
def test_timestamp_is_baghdad_time_stored_in_utc(raw, expected) -> None:
    assert lr.parse_timestamp(raw) == expected


@pytest.mark.parametrize(
    ("status", "counts"),
    [
        ("ملغي", False),
        (" مرفوض ", False),
        ("تم", True),
        ("ملغى", True),  # only the two exact values are excluded (research R3)
        ("", True),
        (None, True),
    ],
)
def test_counts_in_check(status, counts) -> None:
    assert lr.counts_in_check(status) is counts


@pytest.mark.parametrize(
    ("cell", "file_id"),
    [
        ("https://drive.google.com/open?id=1AbC_dEf-GhIjKlMn", "1AbC_dEf-GhIjKlMn"),
        ("https://drive.google.com/file/d/1AbC_dEf-GhIjKlMn/view?usp=sharing", "1AbC_dEf-GhIjKlMn"),
        ("https://drive.google.com/uc?export=download&id=1AbC_dEf-GhIjKlMn", "1AbC_dEf-GhIjKlMn"),
        (
            "https://drive.google.com/open?id=firstFile00001, "
            "https://drive.google.com/open?id=secondFile0002",
            "firstFile00001",
        ),
        ("https://drive.google.com/open?id=fake-ok-front-01", "fake-ok-front-01"),
        ("https://example.com/open?id=1AbC_dEf-GhIjKlMn", None),
        ("صورة", None),
        ("", None),
        (None, None),
    ],
)
def test_drive_file_id(cell, file_id) -> None:
    assert lr.drive_file_id(cell) == file_id


# --- the whole row ---


def _raw(**overrides) -> dict:
    row = {
        "timestamp": "2024/05/12 10:23:45",
        "first_name": " سمير ",
        "second_name": "كاظم",
        "third_name": "جبار",
        "mother_name": "زينب",
        "mother_father_name": "حسن",
        "birth_date": "1990/01/10",
        "family_number": "1234a56789012345o6",
        "phone": "0780 123 4567",
        "front_image": "https://drive.google.com/open?id=fake-ok-front-01",
        "back_image": "https://drive.google.com/open?id=fake-ok-back-001",
        "email_1": "a@example.com",
        "email_2": "",
        "legacy_number": "T3C-001",
        "status": "تم",
    }
    row.update(overrides)
    return row


def test_clean_row_values() -> None:
    row = lr.clean_row(2, _raw())
    assert row["index"] == 2
    assert row["legacy_number"] == "T3C-001"
    assert row["names"] == {"first": "سمير", "second": "كاظم", "third": "جبار"}
    assert row["full_name"] == "سمير كاظم جبار"
    assert row["family_number_file"] == "1234a56789012345o6"
    assert row["family_key"] == "1234A5678901234506"
    assert row["phone_file"] == "0780 123 4567"
    assert row["phone"] == "07801234567"
    assert row["status_text"] == "تم"
    assert row["counts_in_check"] is True
    assert row["extra"] == {
        "mother_name": "زينب",
        "mother_father_name": "حسن",
        "birth_date": "1990/01/10",
        "email_1": "a@example.com",
        "email_2": None,
    }
    assert row["form_submitted_at"] == "2024-05-12T07:23:45+00:00"
    assert row["drive_ids"] == {"front": "fake-ok-front-01", "back": "fake-ok-back-001"}
    assert row["flags"] == []


def test_full_name_skips_empty_parts() -> None:
    assert lr.clean_row(2, _raw(second_name=" "))["full_name"] == "سمير جبار"


def _codes(row: dict) -> list[str]:
    return [f["code"] for f in row["flags"]]


@pytest.mark.parametrize(
    ("overrides", "codes"),
    [
        ({"legacy_number": "x"}, ["legacy_number_missing"]),
        ({"first_name": " "}, ["name_missing"]),
        ({"phone": "0780"}, ["phone_invalid"]),
        ({"phone": ""}, ["phone_missing"]),
        ({"family_number": ""}, ["family_missing"]),
        ({"family_number": "1234A567"}, ["family_length"]),
        (
            {"family_number": "", "phone": "bad"},
            ["phone_invalid", "family_missing", "no_check_keys"],
        ),
    ],
)
def test_row_flags(overrides, codes) -> None:
    assert _codes(lr.clean_row(2, _raw(**overrides))) == codes


def test_missing_image_flag_names_the_side() -> None:
    row = lr.clean_row(2, _raw(back_image="", front_image="لا يوجد"))
    assert row["flags"] == [
        {"code": "image_missing", "side": "front"},
        {"code": "image_missing", "side": "back"},
    ]
    assert row["drive_ids"] == {"front": None, "back": None}


def test_family_length_counts_the_comparison_key() -> None:
    # 18 characters once spaces and dashes are dropped: no flag.
    assert lr.clean_row(2, _raw(family_number="1234-A567 8901 2345 06"))["flags"] == []
