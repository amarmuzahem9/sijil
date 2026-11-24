"""«تم الربط هذا الشهر» on the marketer home (docs/system.md v1.18 §4.2, §6.5; specs/013 US2:
FR-011, FR-012, FR-014; data-model.md › Counting rule). Synthetic data only."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.timeutil import baghdad_month_label
from app.services import link_service
from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import headers_for

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
# 2026-11-30 23:59 and 2026-12-01 00:00 in Baghdad (UTC+3).
LAST_MINUTE_OF_NOVEMBER = datetime(2026, 11, 30, 20, 59, tzinfo=UTC)
FIRST_MINUTE_OF_DECEMBER = datetime(2026, 11, 30, 21, 0, tzinfo=UTC)


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


def _linked(db, marketer, at: datetime, **overrides):
    return request_factory(db, marketer, status="linked", linked_at=at, **overrides)


def _dashboard(client, marketer) -> dict:
    res = client.get("/api/marketer/dashboard", headers=headers_for(client, marketer))
    assert res.status_code == 200, res.json()
    return res.json()


def test_commission_links_and_returns_without_commission(
    client, db, marketer, frozen_clock
) -> None:
    frozen_clock.set(NOW)
    _linked(db, marketer, NOW - timedelta(hours=1))
    _linked(db, marketer, NOW - timedelta(hours=2), type="additional")
    _linked(db, marketer, NOW - timedelta(hours=3), type="return", counts_commission=True)
    _linked(db, marketer, NOW - timedelta(hours=4), type="return", counts_commission=False)

    body = _dashboard(client, marketer)

    assert body["linked_this_month"] == 3
    assert body["linked_without_commission"] == 1
    assert body["month_label"] == baghdad_month_label(NOW)


def test_only_linked_rows_of_this_month_count(
    client, db, make_user, marketer, frozen_clock
) -> None:
    frozen_clock.set(NOW)
    admin = make_user("super_admin")
    _linked(db, marketer, NOW - timedelta(days=30))  # October
    request_factory(db, marketer, status="approved")
    request_factory(db, marketer, status="pending_review")
    request_factory(db, marketer, status="rejected")
    mark_deleted(db, request_factory(db, marketer, status="pending_review"), admin)
    _linked(db, make_user("marketer"), NOW)  # another marketer

    body = _dashboard(client, marketer)

    assert (body["linked_this_month"], body["linked_without_commission"]) == (0, 0)
    assert body["recent_links"] == []


def test_month_starts_at_baghdad_midnight(client, db, marketer, frozen_clock) -> None:
    november = _linked(db, marketer, LAST_MINUTE_OF_NOVEMBER)
    december = _linked(db, marketer, FIRST_MINUTE_OF_DECEMBER)

    frozen_clock.set(LAST_MINUTE_OF_NOVEMBER + timedelta(seconds=30))
    in_november = _dashboard(client, marketer)
    frozen_clock.set(FIRST_MINUTE_OF_DECEMBER + timedelta(days=1))
    in_december = _dashboard(client, marketer)

    assert in_november["linked_this_month"] == 1
    assert [r["id"] for r in in_november["recent_links"]] == [november.id]
    assert in_december["linked_this_month"] == 1
    assert [r["id"] for r in in_december["recent_links"]] == [december.id]


def test_recent_links_are_the_latest_ten_of_this_month(
    client, db, make_user, marketer, frozen_clock
) -> None:
    frozen_clock.set(NOW)
    rows = [_linked(db, marketer, NOW - timedelta(hours=h)) for h in range(12)]
    _linked(db, marketer, NOW - timedelta(days=30))
    _linked(db, make_user("marketer"), NOW)

    recent = _dashboard(client, marketer)["recent_links"]

    assert [r["id"] for r in recent] == [r.id for r in rows[:10]]
    assert set(recent[0]) == {"id", "number_label", "full_name", "linked_at"}
    assert recent[0]["number_label"] == rows[0].number_label
    assert recent[0]["full_name"] == rows[0].full_name
    assert datetime.fromisoformat(recent[0]["linked_at"]) == NOW


def test_an_archived_marketer_keeps_counting(db, make_user, marketer, frozen_clock) -> None:
    """The archived account cannot sign in (§3.6); its links still belong to its month."""
    frozen_clock.set(NOW)
    _linked(db, marketer, NOW)
    admin = make_user("super_admin")
    marketer.is_active = False
    marketer.archived_at = NOW
    marketer.archived_by = admin.id
    db.flush()

    counts = link_service.marketer_counts(db, marketer)

    assert (counts.linked_this_month, counts.linked_without_commission) == (1, 0)


def test_admins_cannot_read_the_marketer_dashboard(client, make_user) -> None:
    admin = make_user("super_admin")
    res = client.get("/api/marketer/dashboard", headers=headers_for(client, admin))
    assert res.status_code == 403
