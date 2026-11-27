"""The requests report of «التقارير والتصدير» (docs/system.md v1.25 §11; specs/019 US1, FR-003 to
FR-006; research R2–R4, R13; contracts/api.md). Synthetic data only.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.timeutil import BAGHDAD, utc_now
from app.models import Area, Plan, Tower
from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import headers_for

URL = "/api/admin/reports/requests"
OCTOBER = {"period": "range", "from": "2026-10-01", "to": "2026-10-31"}
NOVEMBER = {"period": "range", "from": "2026-11-01", "to": "2026-11-30"}


def _baghdad(y: int, m: int, d: int, hh: int = 12, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=BAGHDAD).astimezone(UTC)


_n = iter(range(1, 10_000))


def _place(db, *, plan_active: bool = True):
    n = next(_n)
    area = Area(name=f"منطقة تقرير {n}")
    db.add(area)
    db.flush()
    tower = Tower(code=f"RPT{n:02d}", name=f"برج تقرير {n}", area_id=area.id)
    plan = Plan(name=f"فئة تقرير {n}", trial_price=20000, second_price=35000)
    plan.is_active = plan_active
    db.add_all([tower, plan])
    db.flush()
    return {"area": area, "tower": tower, "plan": plan}


def _req(db, marketer, place, *, at: datetime, **over):
    values = {"submitted_at": at, "otp_verified_at": at}
    status = over.get("status", "approved")
    if status in ("approved", "linked"):
        values["approved_at"] = at
    values.update(over)
    return request_factory(db, marketer, **place, **values)


def _get(client, headers, **params):
    response = client.get(URL, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _numbers(body) -> list[int]:
    return [row["number"] for row in body["rows"]]


@pytest.fixture
def admin(make_user):
    return make_user("super_admin")


@pytest.fixture
def h(client, admin):
    return headers_for(client, admin)


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


def test_submission_date_or_link_date(db, client, h, marketer) -> None:
    """31 October 23:30 Baghdad, linked 2 November (spec US1 scenario 1)."""
    place = _place(db)
    r = _req(
        db,
        marketer,
        place,
        at=_baghdad(2026, 10, 31, 23, 30),
        status="linked",
        linked_at=_baghdad(2026, 11, 2, 10),
    )
    assert r.number in _numbers(_get(client, h, **OCTOBER, date_kind="submitted"))
    assert r.number not in _numbers(_get(client, h, **OCTOBER, date_kind="linked"))
    assert r.number in _numbers(_get(client, h, **NOVEMBER, date_kind="linked"))
    # submitted is the default date kind
    assert r.number in _numbers(_get(client, h, **OCTOBER))


def test_range_edges_are_baghdad_days(db, client, h, marketer) -> None:
    place = _place(db)
    last = _req(db, marketer, place, at=_baghdad(2026, 10, 31, 23, 59))
    first = _req(db, marketer, place, at=_baghdad(2026, 11, 1, 0, 0))
    october = _numbers(_get(client, h, **OCTOBER))
    assert last.number in october and first.number not in october


def test_week_and_month_follow_the_baghdad_clock(db, client, h, marketer, frozen_clock) -> None:
    frozen_clock.set(_baghdad(2026, 11, 27, 15))  # a Friday
    place = _place(db)
    saturday = _req(db, marketer, place, at=_baghdad(2026, 11, 21, 0, 0))
    friday_before = _req(db, marketer, place, at=_baghdad(2026, 11, 20, 23, 59))
    first_of_month = _req(db, marketer, place, at=_baghdad(2026, 11, 1, 0, 0))
    october = _req(db, marketer, place, at=_baghdad(2026, 10, 31, 23, 59))
    week = _numbers(_get(client, h, period="week"))
    month = _numbers(_get(client, h, period="month"))
    assert saturday.number in week and friday_before.number not in week
    assert {saturday.number, friday_before.number, first_of_month.number} <= set(month)
    assert october.number not in month


def test_an_undone_link_is_not_in_the_link_date_filter(db, client, h, marketer) -> None:
    place = _place(db)
    linked = _req(
        db,
        marketer,
        place,
        at=_baghdad(2026, 11, 3),
        status="linked",
        linked_at=_baghdad(2026, 11, 4),
    )
    # An undo clears linked_at and returns the request to approved (013).
    undone = _req(db, marketer, place, at=_baghdad(2026, 11, 3), status="approved")
    body = _get(client, h, **NOVEMBER, date_kind="linked")
    assert linked.number in _numbers(body)
    assert undone.number not in _numbers(body)
    assert all(row["status"] == "linked" for row in body["rows"])


def test_each_filter_alone_and_together(db, client, h, make_user) -> None:
    m1, m2 = make_user("marketer"), make_user("marketer")
    a, b = _place(db), _place(db)
    at = _baghdad(2026, 11, 5)
    r1 = _req(db, m1, a, at=at, status="approved", type="new")
    r2 = _req(db, m1, b, at=at, status="pending_review", type="additional")
    r3 = _req(db, m2, a, at=at, status="rejected", type="return")
    r4 = _req(db, m2, b, at=at, status="linked", type="new", linked_at=at)
    everyone = {r1.number, r2.number, r3.number, r4.number}

    def numbers(**params) -> set[int]:
        return set(_numbers(_get(client, h, **NOVEMBER, **params))) & everyone

    assert numbers() == everyone
    assert numbers(area_id=a["area"].id) == {r1.number, r3.number}
    assert numbers(tower_id=b["tower"].id) == {r2.number, r4.number}
    assert numbers(plan_id=a["plan"].id) == {r1.number, r3.number}
    assert numbers(marketer_id=m2.id) == {r3.number, r4.number}
    assert numbers(status="rejected") == {r3.number}
    assert numbers(type="new") == {r1.number, r4.number}
    assert numbers(marketer_id=m1.id, tower_id=a["tower"].id) == {r1.number}
    assert numbers(marketer_id=m1.id, status="linked") == set()


def test_a_deleted_request_shows_its_kept_fields_only(db, client, h, admin, marketer) -> None:
    place = _place(db)
    r = _req(db, marketer, place, at=_baghdad(2026, 11, 6), status="rejected")
    mark_deleted(db, r, admin)
    body = _get(client, h, **NOVEMBER, tower_id=place["tower"].id)
    [row] = body["rows"]
    assert row["number"] == r.number
    assert row["deleted"] is True
    assert row["name"] is None
    assert row["status"] == "rejected"
    assert row["tower"] == f"{place['tower'].name} ({place['tower'].code})"


def test_paging_and_order(db, client, h, marketer) -> None:
    place = _place(db)
    start = _baghdad(2026, 11, 1, 8)
    made = [_req(db, marketer, place, at=start + timedelta(minutes=i)) for i in range(51)]
    newest_first = [r.number for r in reversed(made)]
    first = _get(client, h, **NOVEMBER, tower_id=place["tower"].id)
    assert first["total"] == 51 and first["page"] == 1 and first["page_size"] == 50
    assert _numbers(first) == newest_first[:50]
    second = _get(client, h, **NOVEMBER, tower_id=place["tower"].id, page=2)
    assert _numbers(second) == newest_first[50:]


def test_summaries_add_up_to_the_total(db, client, h, make_user) -> None:
    m1, m2 = make_user("marketer"), make_user("marketer")
    a, b = _place(db), _place(db)
    at = _baghdad(2026, 11, 7)
    for marketer, place, status in [
        (m1, a, "approved"),
        (m1, a, "approved"),
        (m1, b, "rejected"),
        (m2, b, "pending_review"),
        (m2, a, "linked"),
    ]:
        _req(
            db, marketer, place, at=at, status=status, linked_at=at if status == "linked" else None
        )
    body = _get(client, h, **NOVEMBER, marketer_id=m1.id)
    assert body["total"] == 3
    summary = body["summary"]
    for key in ("by_status", "by_tower", "by_marketer"):
        assert sum(item["count"] for item in summary[key]) == body["total"], key
    assert {s["status"]: s["count"] for s in summary["by_status"]} == {"approved": 2, "rejected": 1}
    assert {t["tower_id"]: t["count"] for t in summary["by_tower"]} == {
        a["tower"].id: 2,
        b["tower"].id: 1,
    }
    assert summary["by_marketer"] == [{"marketer_id": m1.id, "marketer": m1.name, "count": 3}]


def test_stored_names_and_archived_marketer(db, client, h, admin, make_user) -> None:
    marketer = make_user("marketer")
    place = _place(db)
    stored_tower = place["tower"].name
    r = _req(db, marketer, place, at=_baghdad(2026, 11, 8))
    place["tower"].name = "اسم جديد للبرج"
    marketer.is_active = False
    marketer.archived_at = utc_now()
    marketer.archived_by = admin.id
    db.flush()
    [row] = _get(client, h, **NOVEMBER, tower_id=place["tower"].id)["rows"]
    assert row["number"] == r.number
    assert row["tower"] == f"{stored_tower} ({place['tower'].code})"
    assert row["marketer"] == marketer.name
    assert row["plan"] == place["plan"].name


def test_options_include_inactive_and_archived(db, client, h, admin, make_user) -> None:
    archived = make_user("marketer")
    archived.is_active = False
    archived.archived_at = utc_now()
    archived.archived_by = admin.id
    place = _place(db, plan_active=False)
    db.flush()
    response = client.get("/api/admin/reports/options", headers=h)
    assert response.status_code == 200
    body = response.json()
    [m] = [m for m in body["marketers"] if m["id"] == archived.id]
    assert m == {"id": archived.id, "name": archived.name, "archived": True, "active": False}
    [p] = [p for p in body["plans"] if p["id"] == place["plan"].id]
    assert p["active"] is False
    [t] = [t for t in body["towers"] if t["id"] == place["tower"].id]
    assert t == {
        "id": place["tower"].id,
        "code": place["tower"].code,
        "name": place["tower"].name,
        "area_id": place["area"].id,
        "active": True,
    }
    assert any(a["id"] == place["area"].id for a in body["areas"])
    # admins are not marketers
    assert admin.id not in {m["id"] for m in body["marketers"]}


@pytest.mark.parametrize(
    "params",
    [
        {"period": "range", "from": "2026-11-02", "to": "2026-11-01"},
        {"period": "range", "from": "2026-11-01"},
        {"period": "range"},
    ],
)
def test_period_invalid(client, h, params) -> None:
    response = client.get(URL, params=params, headers=h)
    assert response.status_code == 422
    assert response.json()["code"] == "period_invalid"


@pytest.mark.parametrize(
    "params",
    [
        {},  # the period is required
        {"period": "year"},
        {"period": "month", "status": "draft"},
        {"period": "month", "type": "other"},
        {"period": "month", "date_kind": "approved"},
        {"period": "month", "page": 0},
    ],
)
def test_bad_parameters(client, h, params) -> None:
    assert client.get(URL, params=params, headers=h).status_code == 422
