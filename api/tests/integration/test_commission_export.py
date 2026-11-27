"""«تصدير» of «العمولات» (docs/system.md v1.25 §9; specs/019 US3, FR-015, SC-005; research R11;
contracts/api.md). The sheet is built from 017's own report and details, so a paid month keeps
its locked figures after a tier change. Default tiers: 0 → 5,000; 30 → 7,000; 50 → 10,000.
Synthetic data only.
"""

import io
from datetime import UTC, date, datetime

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.core.timeutil import BAGHDAD
from app.models import AuditLog, RewardTier
from app.schemas.admin_links import UnlinkIn
from app.services import link_service
from tests.helpers.requests import pay_month, request_factory
from tests.helpers.review import admin_with, headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
PAID_AT = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
UNDO_AT = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
SEPTEMBER = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)
OCTOBER = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
NOVEMBER = datetime(2026, 11, 12, 9, 0, tzinfo=UTC)
EXPORT = "/api/admin/commissions/export"

KIND_COUNTED = "محسوب"
KIND_WITHOUT = "بلا عمولة"


@pytest.fixture
def boss(make_user):
    return admin_with(make_user, "commissions", "link", name="أدمن عمولات تجريبي")


@pytest.fixture
def alice(make_user):
    return make_user("marketer", name="أ مسوّق تجريبي")


@pytest.fixture
def bob(make_user):
    return make_user("marketer", name="ب مسوّق تجريبي")


@pytest.fixture
def world(db, boss, alice, bob, frozen_clock):
    """A paid October for alice (one undone after payment), an unpaid October for bob, an
    unpaid November for both (with a «بلا عمولة» return and a request paid in September), and
    then a tier change."""
    frozen_clock.set(NOW)
    paid = [request_factory(db, alice, status="linked", linked_at=OCTOBER) for _ in range(3)]
    pay_month(db, alice, date(2026, 10, 1), boss, paid, rate=5000, at=PAID_AT)
    frozen_clock.set(UNDO_AT)
    link_service.unlink(
        db,
        boss,
        paid[0].id,
        UnlinkIn(reason="by_mistake", link_id=link_service._current_link_id(db, paid[0])),
    )
    frozen_clock.set(NOW)
    for _ in range(2):
        request_factory(db, bob, status="linked", linked_at=OCTOBER)
    for _ in range(2):
        request_factory(db, alice, status="linked", linked_at=NOVEMBER)
    request_factory(
        db, alice, status="linked", linked_at=NOVEMBER, type="return", counts_commission=False
    )
    earlier = request_factory(db, bob, status="linked", linked_at=SEPTEMBER)
    pay_month(db, bob, date(2026, 9, 1), boss, [earlier], at=PAID_AT)
    earlier.linked_at = NOVEMBER  # relinked in November after its September payment
    request_factory(db, bob, status="linked", linked_at=NOVEMBER)
    # A tier change after the October payment: 0 → 6,000 for every unpaid month (§9).
    tier = db.scalar(select(RewardTier).where(RewardTier.min_count == 0))
    tier.rate = 6000
    db.flush()
    return {"paid": paid}


def _export(client, user, month: str):
    return client.get(EXPORT, params={"month": month}, headers=headers_for(client, user))


def _sheets(response) -> tuple[list[dict], list[dict]]:
    wb = load_workbook(io.BytesIO(response.content))
    assert wb.sheetnames == ["العمولات", "الطلبات"]
    out = []
    for ws in wb.worksheets:
        assert ws.sheet_view.rightToLeft is True
        rows = list(ws.iter_rows(values_only=True))
        out.append([dict(zip(rows[0], r, strict=True)) for r in rows[1:]])
    return out[0], out[1]


def _report(client, user, month: str) -> dict:
    res = client.get(f"/api/admin/commissions?month={month}", headers=headers_for(client, user))
    assert res.status_code == 200
    return res.json()


def _detail(client, user, month: str, marketer_id: int) -> dict:
    res = client.get(
        f"/api/admin/commissions/{month}/marketers/{marketer_id}",
        headers=headers_for(client, user),
    )
    assert res.status_code == 200
    return res.json()


@pytest.mark.parametrize("month", ["2026-10", "2026-11"])
def test_the_sheets_equal_the_page(client, boss, world, month) -> None:
    response = _export(client, boss, month)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert f'filename="sijil-commissions-{month}.xlsx"' in response.headers["content-disposition"]
    marketers, lines = _sheets(response)
    report = _report(client, boss, month)
    *rows, total = marketers
    assert len(rows) == len(report["rows"])
    for api, cell in zip(report["rows"], rows, strict=True):
        assert cell["المسوّق"] == api["marketer_name"]
        assert cell["العدد"] == api["count"]
        assert cell["بلا عمولة"] == api["without_commission"]
        assert cell["مدفوع سابقاً"] == api["paid_before"]
        assert cell["سعر المشترك"] == api["rate"]
        assert cell["المبلغ"] == api["amount"]
        paid = api["payment"]
        assert cell["الدفع"] == ("تم الدفع" if paid else "غير مدفوع")
        assert cell["دفع بواسطة"] == (paid["paid_by_name"] if paid else None)
        assert cell["العدد اليوم"] == (paid["count_today"] if paid else None)
    assert total["المسوّق"] == "المجموع"
    assert total["المبلغ"] == report["total_amount"]
    assert total["العدد"] == sum(r["count"] for r in report["rows"])

    expected = set()
    for api in report["rows"]:
        detail = _detail(client, boss, month, api["marketer_id"])
        name = api["marketer_name"]
        expected |= {(name, d["number_label"], KIND_COUNTED) for d in detail["counted"]}
        expected |= {(name, d["number_label"], KIND_WITHOUT) for d in detail["without_commission"]}
        expected |= {
            (name, d["number_label"], f"مدفوع سابقاً ({d['paid_month']})")
            for d in detail["paid_before"]
        }
    got = {(line["المسوّق"], line["رقم الطلب"], line["العمولة"]) for line in lines}
    assert got == expected
    assert len(lines) == len(expected)


def test_a_paid_month_keeps_its_locked_figures(client, boss, alice, world) -> None:
    marketers, _ = _sheets(_export(client, boss, "2026-10"))
    [row] = [r for r in marketers if r["المسوّق"] == alice.name]
    # Paid at 5,000 before the tier change; one paid request was undone after the payment.
    assert (row["العدد"], row["سعر المشترك"], row["المبلغ"]) == (3, 5000, 15000)
    assert row["الدفع"] == "تم الدفع" and row["العدد اليوم"] == 2
    assert row["وقت الدفع"] == PAID_AT.astimezone(BAGHDAD).strftime("%Y-%m-%d %H:%M")
    undone = world["paid"][0]
    note = row["تراجع بعد الدفع"]
    assert undone.number_label in note
    assert "ضُغط بالخطأ" in note
    assert UNDO_AT.astimezone(BAGHDAD).strftime("%Y-%m-%d %H:%M") in note


def test_an_unpaid_month_uses_todays_tiers(client, boss, bob, world) -> None:
    marketers, _ = _sheets(_export(client, boss, "2026-10"))
    [row] = [r for r in marketers if r["المسوّق"] == bob.name]
    assert (row["العدد"], row["سعر المشترك"], row["المبلغ"]) == (2, 6000, 12000)
    assert row["الدفع"] == "غير مدفوع" and row["تراجع بعد الدفع"] is None


def test_an_archived_marketer_keeps_their_row(db, client, boss, bob, world) -> None:
    bob.is_active, bob.archived_at, bob.archived_by = False, NOW, boss.id
    db.flush()
    marketers, _ = _sheets(_export(client, boss, "2026-10"))
    assert bob.name in [r["المسوّق"] for r in marketers]


def test_no_phone_or_identity_number(client, db, boss, world) -> None:
    from app.models import Request

    response = _export(client, boss, "2026-11")
    marketers, lines = _sheets(response)
    text = str(marketers) + str(lines)
    for request in db.scalars(select(Request)):
        for value in (request.phone, request.national_id, request.family_number, request.username):
            if value:
                assert value not in text
    for line in lines:
        assert set(line) == {
            "المسوّق",
            "رقم الطلب",
            "الاسم",
            "النوع",
            "البرج",
            "تاريخ الربط",
            "العمولة",
        }


def test_the_export_is_audited(client, db, boss, world) -> None:
    assert _export(client, boss, "2026-10").status_code == 200
    [entry] = db.scalars(select(AuditLog).where(AuditLog.action == "commissions.exported")).all()
    assert entry.actor_id == boss.id
    assert (entry.entity_type, entry.entity_id) == ("commission_month", "2026-10")
    assert entry.after == {"month": "2026-10"}


@pytest.mark.parametrize("who", ["reports", "review", "marketer"])
def test_only_commissions_may_export(client, make_user, world, alice, who) -> None:
    user = alice if who == "marketer" else admin_with(make_user, who)
    assert _export(client, user, "2026-10").status_code == 403


@pytest.mark.parametrize("month", ["2026-13", "x", "2027-01"])
def test_a_bad_or_future_month(client, boss, world, month) -> None:
    response = _export(client, boss, month)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
