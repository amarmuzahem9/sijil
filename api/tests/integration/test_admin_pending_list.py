"""«طلبات بالانتظار» (specs/010 US1: FR-001, FR-002; research R13). Synthetic data only."""

import pytest

from app.models import RequestReason
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for, pending_request

URL = "/api/admin/requests/pending"


@pytest.fixture
def marketer(make_user):
    return make_user("marketer", name="مسوّق المراجعة")


@pytest.fixture
def five(db, marketer):
    """One pending request per path of 008/009, oldest first, plus decided ones."""
    old = request_factory(db, marketer)
    family = pending_request(
        db, marketer, [("family_exists", old, {})], type="additional", minutes_ago=50
    )
    edited = pending_request(
        db, marketer, [("numbers_edited", None, {"fields": ["family_number"]})], minutes_ago=40
    )
    conflict = pending_request(db, marketer, [("numbers_conflict", old, {})], minutes_ago=30)
    by_identity = pending_request(
        db,
        marketer,
        [
            ("return", old, {"basis": "identity"}),
            ("numbers_edited", None, {"fields": ["national_id"]}),
        ],
        type="return",
        minutes_ago=20,
    )
    by_phone = pending_request(
        db, marketer, [("return", old, {"basis": "phone"})], type="return", minutes_ago=10
    )
    request_factory(db, marketer, status="approved")
    request_factory(db, marketer, status="rejected")
    return [family, edited, conflict, by_identity, by_phone]


def test_review_admin_sees_the_five_oldest_first(client, make_user, five, marketer) -> None:
    res = client.get(URL, headers=headers_for(client, admin_with(make_user, "review")))

    assert res.status_code == 200, res.json()
    body = res.json()
    assert body["total"] == 5
    assert [i["id"] for i in body["items"]] == [r.id for r in five]
    first = body["items"][0]
    assert first == {
        "id": five[0].id,
        "number_label": five[0].number_label,
        "type": "additional",
        "reasons": ["family_exists"],
        "marketer_name": "مسوّق المراجعة",
        "full_name": five[0].full_name,
        "tower_code": five[0].tower_code,
        "tower_name": five[0].tower_name,
        "submitted_at": first["submitted_at"],
    }
    assert body["items"][3]["reasons"] == ["return", "numbers_edited"]


def test_filter_by_reason(client, make_user, five) -> None:
    h = headers_for(client, admin_with(make_user, "review"))

    conflict = client.get(URL, params={"reason": "numbers_conflict"}, headers=h).json()
    assert [i["id"] for i in conflict["items"]] == [five[2].id]
    assert conflict["total"] == 1

    # A request with two reasons appears under both.
    edited = client.get(URL, params={"reason": "numbers_edited"}, headers=h).json()
    assert [i["id"] for i in edited["items"]] == [five[1].id, five[3].id]
    returns = client.get(URL, params={"reason": "return"}, headers=h).json()
    assert [i["id"] for i in returns["items"]] == [five[3].id, five[4].id]


def test_reason_no_longer_applying_is_left_out(client, db, make_user, five) -> None:
    row = db.query(RequestReason).filter_by(request_id=five[2].id).one()
    row.state = "not_applicable"
    db.flush()
    h = headers_for(client, admin_with(make_user, "review"))

    body = client.get(URL, params={"reason": "numbers_conflict"}, headers=h).json()
    assert body["items"] == []
    item = next(i for i in client.get(URL, headers=h).json()["items"] if i["id"] == five[2].id)
    assert item["reasons"] == []


def test_unknown_reason_is_422(client, make_user) -> None:
    h = headers_for(client, admin_with(make_user, "review"))
    assert client.get(URL, params={"reason": "rude"}, headers=h).status_code == 422


def test_main_admin_sees_the_list(client, make_user, five) -> None:
    res = client.get(URL, headers=headers_for(client, make_user("super_admin")))
    assert res.status_code == 200
    assert res.json()["total"] == 5


@pytest.mark.parametrize("who", ["settings_admin", "marketer"])
def test_others_are_refused(client, make_user, five, who) -> None:
    user = admin_with(make_user, "settings") if who == "settings_admin" else make_user("marketer")
    res = client.get(URL, headers=headers_for(client, user))
    assert res.status_code == 403
    assert res.json()["code"] == "forbidden"
