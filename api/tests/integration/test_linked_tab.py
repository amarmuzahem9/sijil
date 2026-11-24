"""The marketer's «تم الربط» tab and request page (specs/013 US2: FR-017 to FR-019, research R8).

Synthetic data only.
"""

from datetime import UTC, datetime, timedelta

import pytest

from tests.helpers.requests import request_factory
from tests.helpers.review import headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.fixture
def h(client, marketer):
    return headers_for(client, marketer)


def test_linked_tab_is_ordered_by_link_time(client, db, h, marketer) -> None:
    # Submitted in one order, linked in the opposite one.
    first = request_factory(
        db, marketer, status="linked", submitted_at=NOW - timedelta(days=3), linked_at=NOW
    )
    second = request_factory(
        db,
        marketer,
        status="linked",
        submitted_at=NOW - timedelta(days=1),
        linked_at=NOW - timedelta(days=1),
    )

    res = client.get("/api/requests", params={"status": "linked"}, headers=h)

    assert res.status_code == 200, res.json()
    items = res.json()["items"]
    assert [i["id"] for i in items] == [first.id, second.id]
    assert datetime.fromisoformat(items[0]["linked_at"]) == NOW


def test_other_tabs_keep_the_submission_order(client, db, h, marketer) -> None:
    older = request_factory(db, marketer, submitted_at=NOW - timedelta(days=2))
    newer = request_factory(db, marketer, submitted_at=NOW - timedelta(days=1))
    items = client.get("/api/requests", params={"status": "approved"}, headers=h).json()["items"]
    assert [i["id"] for i in items] == [newer.id, older.id]
    assert all(i["linked_at"] is None for i in items)


def test_request_page_has_the_link_time_and_never_the_linker(client, db, h, marketer) -> None:
    linked = request_factory(db, marketer, status="linked", linked_at=NOW)
    accepted = request_factory(db, marketer)

    linked_body = client.get(f"/api/requests/{linked.id}", headers=h).json()
    accepted_body = client.get(f"/api/requests/{accepted.id}", headers=h).json()
    listed = client.get("/api/requests", headers=h).json()["items"]

    assert datetime.fromisoformat(linked_body["linked_at"]) == NOW
    assert linked_body["link_message"] is not None
    assert accepted_body["linked_at"] is None
    for body in (linked_body, accepted_body, *listed):
        assert "linked_by" not in body
        assert "linked_by_name" not in body
