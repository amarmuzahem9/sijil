"""The admin home counts (specs/010 US5: FR-021; research R10). Days and months are Baghdad time.
Synthetic data only."""

from datetime import UTC, datetime

import pytest

from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for

# 09:00 in Baghdad on 24 November 2026.
NOW = datetime(2026, 11, 24, 6, 0, tzinfo=UTC)
EARLIER_THIS_MONTH = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
LAST_MONTH = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
KEYS = {"submitted", "approved", "pending", "linked", "rejected"}


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


def _home(client, h):
    res = client.get("/api/admin/home", headers=h)
    assert res.status_code == 200, res.json()
    return res.json()


def _submitted(db, marketer, at, status, **extra):
    return request_factory(
        db,
        marketer,
        status=status,
        submitted_at=at,
        otp_verified_at=at,
        approved_at=at if status == "approved" else None,
        **extra,
    )


def test_today_and_month(client, db, make_user, marketer, frozen_clock) -> None:
    frozen_clock.set(NOW)
    today = datetime(2026, 11, 24, 5, 0, tzinfo=UTC)
    _submitted(db, marketer, today, "approved")  # the automatic approval
    _submitted(db, marketer, today, "pending_review")
    _submitted(db, marketer, today, "rejected", rejected_at=today)
    _submitted(db, marketer, EARLIER_THIS_MONTH, "approved")
    _submitted(db, marketer, LAST_MONTH, "approved")

    body = _home(client, headers_for(client, make_user("super_admin")))

    assert body == {
        "today": {"submitted": 3, "approved": 1, "pending": 1, "linked": 0, "rejected": 1},
        "month": {"submitted": 4, "approved": 2, "pending": 1, "linked": 0, "rejected": 1},
    }


def test_counts_go_by_the_time_of_each_step(client, db, make_user, marketer, frozen_clock) -> None:
    """Approved and rejected count when they happened, not when the request was submitted
    (system.md v1.13 §10 item 1); pending is the current number in both rows."""
    frozen_clock.set(NOW)
    old = _submitted(db, marketer, EARLIER_THIS_MONTH, "pending_review")
    old.status, old.approved_at = "approved", datetime(2026, 11, 24, 5, 30, tzinfo=UTC)
    _submitted(db, marketer, LAST_MONTH, "pending_review")
    db.flush()

    body = _home(client, headers_for(client, make_user("super_admin")))

    assert body["today"] == {
        "submitted": 0,
        "approved": 1,
        "pending": 1,
        "linked": 0,
        "rejected": 0,
    }
    assert body["month"]["submitted"] == 1
    assert body["month"]["pending"] == 1


def test_baghdad_day_bounds(client, db, make_user, marketer, frozen_clock) -> None:
    frozen_clock.set(NOW)
    # 23:30 in Baghdad on the 23rd: yesterday. 00:30 on the 24th: today.
    _submitted(db, marketer, datetime(2026, 11, 23, 20, 30, tzinfo=UTC), "pending_review")
    _submitted(db, marketer, datetime(2026, 11, 23, 21, 30, tzinfo=UTC), "pending_review")

    body = _home(client, headers_for(client, make_user("super_admin")))

    assert body["today"]["submitted"] == 1
    assert body["month"]["submitted"] == 2


def test_month_starts_in_baghdad(client, db, make_user, marketer, frozen_clock) -> None:
    # 1 December 00:30 in Baghdad is still 30 November in UTC.
    frozen_clock.set(datetime(2026, 11, 30, 21, 40, tzinfo=UTC))
    _submitted(db, marketer, datetime(2026, 11, 30, 21, 30, tzinfo=UTC), "pending_review")
    _submitted(db, marketer, datetime(2026, 11, 30, 20, 30, tzinfo=UTC), "pending_review")

    body = _home(client, headers_for(client, make_user("super_admin")))

    assert body["month"]["submitted"] == 1


def test_any_admin_but_no_marketer(client, db, make_user, marketer) -> None:
    body = _home(client, headers_for(client, admin_with(make_user, "settings")))
    assert set(body) == {"today", "month"}
    for row in body.values():
        assert set(row) == KEYS
        assert all(type(v) is int for v in row.values())

    res = client.get("/api/admin/home", headers=headers_for(client, marketer))
    assert res.status_code == 403
    assert client.get("/api/admin/home").status_code == 401
