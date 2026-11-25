"""SAS subscribers stay out of requests, links, counters and notifications (specs/015 US4:
FR-016–FR-020, SC-006). The import runs through the API with the synthetic file, which holds the
username of an approved request and phones of live, rejected and deleted requests; every request
row, link row, list and count is compared before and after. Synthetic data only."""

import pytest
from sqlalchemy import func, select

from app.models import Notification, Request, RequestLink, SasSubscriber
from tests.helpers import sas
from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for
from tests.helpers.submit import marketer_headers
from tests.integration.test_legacy_isolation import _snapshot

URL = "/api/admin/imports/sas/previews"
SAMPLE = sas.fixture_bytes("sas_sample.csv")


def _requests(db) -> list[tuple]:
    db.expire_all()
    return [
        (
            r.id,
            r.status,
            r.username,
            r.phone,
            r.approved_at,
            r.linked_at,
            r.linked_by,
            r.counts_commission,
            r.deleted_at,
        )
        for r in db.scalars(select(Request).order_by(Request.id))
    ]


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


@pytest.fixture
def world(db, make_user) -> dict:
    sas.seed_towers(db)
    marketer = make_user("marketer")
    approved = request_factory(db, marketer, phone="07810000015", username="ALM03-07810000015")
    linked = request_factory(db, marketer, status="linked", phone="07810000001")
    request_factory(db, marketer, status="rejected", phone="07810000018")
    deleted = request_factory(db, marketer, status="pending_review", phone="07810000003")
    mark_deleted(db, deleted, marketer)
    pending = request_factory(db, marketer, status="pending_review", phone="07810000014")
    db.flush()
    return {
        "marketer": marketer,
        "approved": approved,
        "linked": linked,
        "pending": pending,
    }


def _import(client, reporter, towers_id: int) -> dict:
    h = headers_for(client, reporter)
    preview = client.post(URL, files={"file": ("sas.csv", SAMPLE, "text/csv")}, headers=h).json()
    flagged = {row["index"]: row for row in preview["flagged"]}
    # The approved request's username is the same subscriber: counted, never flagged (FR-018).
    assert preview["counts"]["same_username_in_sijil"] == 1
    assert 15 not in flagged
    # Rejected and deleted requests never flag a row (§6.1, §7.4).
    assert 18 not in flagged
    assert 4 not in flagged
    choices = [{"index": i, "choice": "import" if i in (2, 9, 14) else "skip"} for i in flagged]
    put = client.put(
        f"{URL}/{preview['id']}/choices",
        json={"choices": choices, "prefixes": [{"prefix": "ZZQ07", "tower_id": towers_id}]},
        headers=h,
    )
    assert put.status_code == 200, put.json()
    done = client.post(f"{URL}/{preview['id']}/confirm", headers=h)
    assert done.status_code == 201, done.json()
    return done.json()


def test_an_import_changes_no_request_link_list_count_or_notification(
    client, db, make_user, world
) -> None:
    main = make_user("super_admin")
    admin_h = headers_for(client, main)
    marketer_h = marketer_headers(client, world["marketer"])
    requests = _requests(db)
    links = _count(db, RequestLink)
    notifications = _count(db, Notification)
    before = _snapshot(client, admin_h, marketer_h)

    reporter = admin_with(make_user, "reports")
    summary = _import(client, reporter, sas.seed_towers(db)["ALM03"])
    assert summary["added"] > 0

    assert _requests(db) == requests
    assert _count(db, RequestLink) == links
    assert _count(db, Notification) == notifications
    assert _snapshot(client, admin_h, marketer_h) == before
    # The approved request whose username is in the file is still waiting for «تم الربط».
    assert db.get(Request, world["approved"].id).status == "approved"


def test_no_route_deletes_a_sas_subscriber(client, db, make_user, world) -> None:
    reporter = admin_with(make_user, "reports")
    _import(client, reporter, sas.seed_towers(db)["ALM03"])
    sub = db.scalars(select(SasSubscriber)).first()
    main_h = headers_for(client, make_user("super_admin"))
    for path in (
        f"/api/admin/sas-subscribers/{sub.id}",
        f"/api/admin/subscribers/sas/{sub.id}",
        f"/api/admin/imports/sas/subscribers/{sub.id}",
    ):
        assert client.delete(path, headers=main_h).status_code in (404, 405)
    assert db.get(SasSubscriber, sub.id) is not None


def test_a_sas_id_is_not_a_request_number(client, db, make_user, world) -> None:
    reporter = admin_with(make_user, "reports")
    _import(client, reporter, sas.seed_towers(db)["ALM03"])
    reviewer_h = headers_for(client, admin_with(make_user, "review"))
    for text in ("101", "SAS-101", "ALM03-07810000002"):
        res = client.get(f"/api/admin/requests/by-number/{text}", headers=reviewer_h)
        assert res.status_code in (404, 422), (text, res.json())


def test_the_marketer_search_never_finds_a_sas_subscriber(client, db, make_user, world) -> None:
    reporter = admin_with(make_user, "reports")
    _import(client, reporter, sas.seed_towers(db)["ALM03"])
    marketer_h = marketer_headers(client, world["marketer"])
    for q in ("07810000002", "ALM03-07810000002", "KZF06", "مشترك تجريبي"):
        res = client.get("/api/requests", params={"q": q}, headers=marketer_h)
        assert res.status_code == 200, res.json()
        assert "ALM03-07810000002" not in res.text
        assert "KZF06-07810000002" not in res.text
