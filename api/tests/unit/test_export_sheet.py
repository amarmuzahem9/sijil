"""The sheet of a requests export (docs/system.md v1.25 §11; specs/019 FR-007, FR-008, FR-010,
FR-012; research R9). Synthetic values only.
"""

import io
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from openpyxl import load_workbook

from app.services.export_sheet import (
    BASE_HEADERS,
    IDENTITY_HEADERS,
    MISSING_IMAGE,
    ExportRow,
    columns,
    request_workbook,
)

ROW = ExportRow(
    number=1001,
    full_name="تجربة اختبار نموذج",
    phone="07900000001",
    username="TST01-07900000001",
    area="منطقة تجريبية",
    tower="برج تجريبي (TST01)",
    plan="فئة تجريبية",
    trial_price=20000,
    second_price=35000,
    marketer="مسوّق تجريبي",
    type="new",
    status="linked",
    submitted_at=datetime(2026, 11, 2, 6, 30, tzinfo=UTC),  # 09:30 Baghdad
    approved_at=datetime(2026, 11, 2, 6, 31, tzinfo=UTC),
    linked_at=datetime(2026, 11, 3, 21, 15, tzinfo=UTC),  # 00:15 on 4 November, Baghdad
    address="حي تجريبي",
    landmark="قرب نقطة تجريبية",
    lat=34.7,
    lng=43.68,
    rejection_reason=None,
    deleted=False,
    deletion_reason=None,
    national_id="199000000001",
    family_number="1000A0000000000001",
    birth_date=date(1990, 1, 1),
    issue_date=date(2020, 1, 1),
    expiry_date=date(2030, 1, 1),
    birth_place="بغداد",
    issuing_authority="جهة تجريبية",
)


def _sheet(data: bytes):
    return load_workbook(io.BytesIO(data)).active


def _table(ws) -> list[dict[str, object]]:
    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]
    return [dict(zip(headers, r, strict=True)) for r in rows[1:]]


def test_base_columns_have_no_identity_header() -> None:
    headers = [h for _, h in columns(identity=False)]
    assert headers == list(BASE_HEADERS)
    assert not set(headers) & set(IDENTITY_HEADERS)
    for expected in (
        "رقم الطلب",
        "الاسم الكامل",
        "الهاتف",
        "اليوزر",
        "المنطقة",
        "البرج",
        "الفئة",
        "السعر التجريبي",
        "السعر الثاني",
        "المسوّق",
        "النوع",
        "الحالة",
        "تاريخ التقديم",
        "تاريخ القبول",
        "تاريخ الربط",
        "العنوان",
        "أقرب نقطة",
        "رابط الموقع",
        "سبب الرفض",
        "محذوف",
        "سبب الحذف",
    ):
        assert expected in headers


def test_identity_columns_are_added_with_the_images() -> None:
    headers = [h for _, h in columns(identity=True)]
    assert headers == list(BASE_HEADERS) + list(IDENTITY_HEADERS)
    for expected in ("الرقم الوطني", "الرقم العائلي", "صورة الوجه", "صورة الظهر"):
        assert expected in IDENTITY_HEADERS


def test_a_base_sheet_carries_no_identity_value() -> None:
    ws = _sheet(request_workbook([ROW], identity=False, images={}))
    text = str(list(ws.iter_rows(values_only=True)))
    for value in (ROW.national_id, ROW.family_number, "1990-01-01", "جهة تجريبية", "cards/"):
        assert value not in text


def test_right_to_left_frozen_header_and_values() -> None:
    ws = _sheet(request_workbook([ROW], identity=False, images={}))
    assert ws.sheet_view.rightToLeft is True
    assert ws.freeze_panes == "A2"
    [row] = _table(ws)
    assert row["رقم الطلب"] == "T3C-1001"
    assert row["الاسم الكامل"] == ROW.full_name
    assert row["الحالة"] == "تم الربط"
    assert row["النوع"] == "جديد"
    assert row["تاريخ التقديم"] == "2026-11-02 09:30"
    assert row["تاريخ الربط"] == "2026-11-04 00:15"
    assert row["السعر التجريبي"] == 20000 and isinstance(row["السعر التجريبي"], int)
    assert row["رابط الموقع"] == "https://maps.google.com/?q=34.7,43.68"
    assert row["محذوف"] is None


@pytest.mark.parametrize("value", ["=1+1", "+9647801234567", "-x", "@a", '=HYPERLINK("x")'])
def test_text_never_becomes_a_formula(value) -> None:
    data = request_workbook(
        [replace(ROW, full_name=value, address=value, landmark=value)], identity=True, images={}
    )
    ws = _sheet(data)
    for cells in ws.iter_rows(min_row=2):
        for cell in cells:
            assert cell.data_type != "f", cell.coordinate
    [row] = _table(ws)
    assert row["الاسم الكامل"] == value
    assert row["العنوان"] == value


def test_a_deleted_row_keeps_only_its_kept_fields() -> None:
    deleted = replace(
        ROW,
        full_name=None,
        phone=None,
        username=None,
        address=None,
        landmark=None,
        lat=None,
        lng=None,
        national_id=None,
        family_number=None,
        birth_date=None,
        issue_date=None,
        expiry_date=None,
        birth_place=None,
        issuing_authority=None,
        status="rejected",
        linked_at=None,
        approved_at=None,
        rejection_reason="صورة البطاقة غير واضحة",
        deleted=True,
        deletion_reason="طلب مكرر",
    )
    ws = _sheet(request_workbook([deleted], identity=True, images={}))
    [row] = _table(ws)
    assert row["محذوف"] == "محذوف"
    assert row["سبب الحذف"] == "طلب مكرر"
    assert row["رقم الطلب"] == "T3C-1001"
    assert row["البرج"] == ROW.tower
    for header in ("الاسم الكامل", "الهاتف", "اليوزر", "العنوان", "رابط الموقع", "الرقم الوطني"):
        assert row[header] is None, header
    # A deleted request has no images (§7.4): no link, no «missing» note.
    assert row["صورة الوجه"] is None and row["صورة الظهر"] is None


def test_image_cells_link_into_cards_and_missing_images_say_so() -> None:
    ws = _sheet(request_workbook([ROW], identity=True, images={1001: {"front"}}))
    headers = [c.value for c in ws[1]]
    front = ws.cell(row=2, column=headers.index("صورة الوجه") + 1)
    back = ws.cell(row=2, column=headers.index("صورة الظهر") + 1)
    assert front.value == "T3C-1001-front.jpg"
    assert front.hyperlink is not None
    assert front.hyperlink.target == "cards/T3C-1001-front.jpg"
    assert back.value == MISSING_IMAGE == "الصورة غير متوفرة"
    assert back.hyperlink is None
    [row] = _table(ws)
    assert row["الرقم الوطني"] == ROW.national_id
    assert row["تاريخ الميلاد"] == "1990-01-01"


def test_rows_keep_their_order() -> None:
    rows = [replace(ROW, number=n) for n in (1003, 1001, 1002)]
    ws = _sheet(request_workbook(rows, identity=False, images={}))
    assert [r["رقم الطلب"] for r in _table(ws)] == ["T3C-1003", "T3C-1001", "T3C-1002"]
