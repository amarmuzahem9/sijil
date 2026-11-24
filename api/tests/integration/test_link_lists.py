"""«بانتظار الربط» lists (specs/013 US1 FR-001 to FR-003, SC-005; research R7; contracts/api.md).

Synthetic data only.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest

from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)

ROW_KEYS = {
    "id",
    "number_label",
    "full_name",
    "username",
    "phone",
    "tower_name",
    "tower_code",
    "plan_name",
    "marketer_name",
    "approved_at",
    "linked_at",
    "linked_by_name",
    "link_id",
}


@pytest.fixture
def marketer(make_user):
    return make_user("marketer", name="مسوّق الربط")


@pytest.fixture
def linker(make_user):
    return admin_with(make_user, "link")


@pytest.fixture
def h(client, linker):
    return headers_for(client, linker)


def _awaiting(client, h, **params):
    return client.get("/api/admin/links/awaiting", params=params, headers=h)


def _accepted(db, marketer, days_ago: int, **overrides):
    return request_factory(
        db, marketer, status="approved", approved_at=NOW - timedelta(days=days_ago), **overrides
    )


def test_only_accepted_live_requests_oldest_first(client, db, h, linker, marketer) -> None:
    newer = _accepted(db, marketer, 1)
    older = _accepted(db, marketer, 5)
    request_factory(db, marketer, status="pending_review")
    request_factory(db, marketer, status="rejected")
    request_factory(db, marketer, status="linked")
    mark_deleted(db, request_factory(db, marketer, status="pending_review"), linker)

    res = _awaiting(client, h)

    assert res.status_code == 200, res.json()
    body = res.json()
    assert [r["id"] for r in body["items"]] == [older.id, newer.id]
    assert body["total"] == 2


def test_row_holds_only_the_sas_check_fields(client, db, h, marketer) -> None:
    request = _accepted(db, marketer, 1)

    (row,) = _awaiting(client, h).json()["items"]

    assert set(row) == ROW_KEYS
    assert row == {
        "id": request.id,
        "number_label": request.number_label,
        "full_name": request.full_name,
        "username": request.username,
        "phone": request.phone,
        "tower_name": request.tower_name,
        "tower_code": request.tower_code,
        "plan_name": request.plan_name,
        "marketer_name": "مسوّق الربط",
        "approved_at": row["approved_at"],
        "linked_at": None,
        "linked_by_name": None,
        "link_id": None,
    }
    assert datetime.fromisoformat(row["approved_at"]) == request.approved_at
    # No identity number anywhere in the answer (constitution Principle II, SC-005).
    text = json.dumps(row, ensure_ascii=False)
    assert request.national_id not in text
    assert request.family_number not in text


def test_marketer_name_is_the_current_one(client, db, h, marketer) -> None:
    _accepted(db, marketer, 1)
    marketer.name = "اسم جديد للمسوّق"
    db.flush()
    (row,) = _awaiting(client, h).json()["items"]
    assert row["marketer_name"] == "اسم جديد للمسوّق"


def test_search_by_number_phone_or_username(client, db, h, marketer) -> None:
    target = _accepted(db, marketer, 2, phone="07801234567")
    _accepted(db, marketer, 1, phone="07801234568")
    digits = str(target.number).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))

    for q in (
        str(target.number),
        f"T3C-{target.number}",
        f"#t3c-{digits}",
        "0780 123 4567",
        "+964 780 123 4567",
        target.username.lower(),
    ):
        items = _awaiting(client, h, q=q).json()["items"]
        assert [r["id"] for r in items] == [target.id], q


def test_search_text_that_is_none_of_the_three_finds_nothing(client, db, h, marketer) -> None:
    _accepted(db, marketer, 1)
    for q in ("تجربة", "%%", "ahmed"):
        body = _awaiting(client, h, q=q).json()
        assert (body["items"], body["total"]) == ([], 0), q


@pytest.mark.parametrize("q", ["1", " ", "  ا "])
def test_search_shorter_than_two_is_422(client, h, q) -> None:
    assert _awaiting(client, h, q=q).status_code == 422


def test_offset_and_limit_page_the_list(client, db, h, marketer) -> None:
    ids = [_accepted(db, marketer, days).id for days in (5, 4, 3)]

    first = _awaiting(client, h, limit=2).json()
    second = _awaiting(client, h, limit=2, offset=2).json()

    assert [r["id"] for r in first["items"]] == ids[:2]
    assert [r["id"] for r in second["items"]] == ids[2:]
    assert first["total"] == second["total"] == 3


@pytest.mark.parametrize("limit", [0, 101])
def test_limit_out_of_range_is_422(client, h, limit) -> None:
    assert _awaiting(client, h, limit=limit).status_code == 422


@pytest.mark.parametrize("who", ["review_admin", "marketer"])
def test_without_link_permission_is_403(client, make_user, marketer, who) -> None:
    caller = admin_with(make_user, "review", "delete") if who == "review_admin" else marketer
    assert _awaiting(client, headers_for(client, caller)).status_code == 403


# --- «المربوطة مؤخراً» (specs/013 US3 FR-004; T038) ---


def _recent(client, h, **params):
    return client.get("/api/admin/links/recent", params=params, headers=h)


def test_recent_lists_linked_live_requests_newest_link_first(
    client, db, h, linker, make_user, marketer
) -> None:
    from sqlalchemy import select

    from app.models import RequestLink

    linker_b = admin_with(make_user, "link", name="أدمن ربط ثاني")
    october = request_factory(
        db, marketer, status="linked", linked_at=NOW - timedelta(days=30), linked_by=linker_b.id
    )
    latest = request_factory(db, marketer, status="linked", linked_at=NOW, linked_by=linker_b.id)
    _accepted(db, marketer, 1)
    request_factory(db, marketer, status="rejected")
    mark_deleted(db, request_factory(db, marketer, status="pending_review"), linker)

    body = _recent(client, h).json()

    assert [r["id"] for r in body["items"]] == [latest.id, october.id]
    assert body["total"] == 2
    row = body["items"][0]
    assert set(row) == ROW_KEYS
    assert datetime.fromisoformat(row["linked_at"]) == NOW
    assert row["linked_by_name"] == "أدمن ربط ثاني"
    current = db.scalar(select(RequestLink.id).where(RequestLink.request_id == latest.id))
    assert row["link_id"] == current
    text = json.dumps(body, ensure_ascii=False)
    assert latest.national_id not in text
    assert latest.family_number not in text


def test_recent_search_and_permission(client, db, h, make_user, marketer) -> None:
    target = request_factory(db, marketer, status="linked", phone="07801230001")
    request_factory(db, marketer, status="linked", phone="07801230002")
    for q in (f"T3C-{target.number}", "0780 123 0001", target.username.lower()):
        assert [r["id"] for r in _recent(client, h, q=q).json()["items"]] == [target.id], q
    assert _recent(client, h, q="1").status_code == 422
    other = admin_with(make_user, "review")
    assert _recent(client, headers_for(client, other)).status_code == 403
