"""The workbooks of «التقارير والتصدير» (docs/system.md v1.25 §11; specs/019 FR-007, FR-008, FR-010,
FR-012; research R9).

`columns(identity)` alone decides what a sheet holds: the base set never has an identity column,
so an identity value cannot reach a sheet whose box was not ticked. Every text cell is written as
text (type `s`, quote prefix), so a value beginning with «=», «+», «-» or «@» never runs as a
formula. Sheets are right-to-left; dates are Baghdad time; money is a whole number of IQD.
"""

import io
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.cell import Cell
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from app.core.timeutil import BAGHDAD

MISSING_IMAGE = "الصورة غير متوفرة"
DELETED_MARK = "محذوف"

STATUS_LABELS = {
    "pending_review": "بانتظار المراجعة",
    "approved": "مقبول (بانتظار الربط)",
    "rejected": "مرفوض",
    "linked": "تم الربط",
}
TYPE_LABELS = {"new": "جديد", "additional": "اشتراك إضافي", "return": "إعادة للخدمة"}


@dataclass(frozen=True)
class ExportRow:
    """One request as the export sees it. Erased values of a deleted request are None (§7.4)."""

    number: int
    full_name: str | None
    phone: str | None
    username: str | None
    area: str
    tower: str
    plan: str
    trial_price: int
    second_price: int
    marketer: str
    type: str
    status: str
    submitted_at: datetime
    approved_at: datetime | None
    linked_at: datetime | None
    address: str | None
    landmark: str | None
    lat: float | None
    lng: float | None
    rejection_reason: str | None
    deleted: bool
    deletion_reason: str | None
    national_id: str | None
    family_number: str | None
    birth_date: date | None
    issue_date: date | None
    expiry_date: date | None
    birth_place: str | None
    issuing_authority: str | None


def _when(value: datetime | None) -> str | None:
    return value.astimezone(BAGHDAD).strftime("%Y-%m-%d %H:%M") if value else None


def _day(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _map(row: ExportRow) -> str | None:
    if row.lat is None or row.lng is None:
        return None
    return f"https://maps.google.com/?q={row.lat},{row.lng}"


Getter = Callable[[ExportRow], Any]

_BASE: tuple[tuple[str, Getter], ...] = (
    ("رقم الطلب", lambda r: f"T3C-{r.number}"),
    ("الاسم الكامل", lambda r: r.full_name),
    ("الهاتف", lambda r: r.phone),
    ("اليوزر", lambda r: r.username),
    ("المنطقة", lambda r: r.area),
    ("البرج", lambda r: r.tower),
    ("الفئة", lambda r: r.plan),
    ("السعر التجريبي", lambda r: r.trial_price),
    ("السعر الثاني", lambda r: r.second_price),
    ("المسوّق", lambda r: r.marketer),
    ("النوع", lambda r: TYPE_LABELS.get(r.type, r.type)),
    ("الحالة", lambda r: STATUS_LABELS.get(r.status, r.status)),
    ("تاريخ التقديم", lambda r: _when(r.submitted_at)),
    ("تاريخ القبول", lambda r: _when(r.approved_at)),
    ("تاريخ الربط", lambda r: _when(r.linked_at)),
    ("العنوان", lambda r: r.address),
    ("أقرب نقطة", lambda r: r.landmark),
    ("رابط الموقع", _map),
    ("سبب الرفض", lambda r: r.rejection_reason),
    ("محذوف", lambda r: DELETED_MARK if r.deleted else None),
    ("سبب الحذف", lambda r: r.deletion_reason),
)

# The image columns are filled by `request_workbook` (they need the images that exist).
_FRONT, _BACK = "صورة الوجه", "صورة الظهر"
_IDENTITY: tuple[tuple[str, Getter | None], ...] = (
    ("الرقم الوطني", lambda r: r.national_id),
    ("الرقم العائلي", lambda r: r.family_number),
    ("تاريخ الميلاد", lambda r: _day(r.birth_date)),
    ("تاريخ الإصدار", lambda r: _day(r.issue_date)),
    ("تاريخ النفاذ", lambda r: _day(r.expiry_date)),
    ("محل الولادة", lambda r: r.birth_place),
    ("جهة الإصدار", lambda r: r.issuing_authority),
    (_FRONT, None),
    (_BACK, None),
)

BASE_HEADERS: tuple[str, ...] = tuple(h for h, _ in _BASE)
IDENTITY_HEADERS: tuple[str, ...] = tuple(h for h, _ in _IDENTITY)


def columns(identity: bool) -> list[tuple[str, str]]:
    """(key, header) pairs, in sheet order. The key is the header itself."""
    chosen = BASE_HEADERS + (IDENTITY_HEADERS if identity else ())
    return [(h, h) for h in chosen]


def image_name(number: int, side: str) -> str:
    return f"T3C-{number}-{side}.jpg"


def _put(ws: Worksheet, row: int, column: int, value: Any) -> Cell:
    cell = ws.cell(row=row, column=column)
    if value is None:
        return cell
    cell.value = value
    if isinstance(value, str):
        # Text stays text: never a formula, whatever it begins with (FR-012).
        cell.data_type = "s"
        cell.quotePrefix = True
    return cell


def _sheet(wb: Workbook, title: str, *, first: bool) -> Worksheet:
    ws = wb.active if first else wb.create_sheet()
    assert ws is not None
    ws.title = title
    ws.sheet_view.rightToLeft = True
    ws.freeze_panes = "A2"
    return ws


def _header(ws: Worksheet, headers: Iterable[str]) -> None:
    for i, header in enumerate(headers, start=1):
        _put(ws, 1, i, header).font = Font(bold=True)


def _bytes(wb: Workbook) -> bytes:
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def request_workbook(
    rows: list[ExportRow], *, identity: bool, images: dict[int, set[str]]
) -> bytes:
    """`requests.xlsx`. `images` maps a request number to the sides whose files will be in
    `cards/`; it is only read for an identity export."""
    wb = Workbook()
    ws = _sheet(wb, "الطلبات", first=True)
    getters: list[tuple[str, Getter | None]] = list(_BASE) + (list(_IDENTITY) if identity else [])
    _header(ws, (h for h, _ in getters))
    for r, row in enumerate(rows, start=2):
        for c, (header, getter) in enumerate(getters, start=1):
            if getter is not None:
                _put(ws, r, c, getter(row))
                continue
            if row.deleted:
                continue  # a deleted request has no images (§7.4)
            side = "front" if header == _FRONT else "back"
            if side in images.get(row.number, set()):
                name = image_name(row.number, side)
                cell = _put(ws, r, c, name)
                cell.hyperlink = f"cards/{name}"
            else:
                _put(ws, r, c, MISSING_IMAGE)
    return _bytes(wb)
