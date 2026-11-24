"""notification_service (specs/012 research R5, R7; data-model.md › New table `notifications`).
Synthetic data only."""

from datetime import timedelta

import pytest
from sqlalchemy import inspect, select

from app.errors import AppError
from app.models.notification import Notification
from app.services import notification_service
from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


def test_add_stores_only_ids_kind_reason_and_time(db, marketer, frozen_clock) -> None:
    request = request_factory(db, marketer, status="rejected", rejection_reason="card_unclear")
    row = notification_service.add(db, request, "rejected", "card_unclear")
    db.flush()

    stored = db.get(Notification, row.id)
    assert stored.marketer_id == marketer.id
    assert stored.request_id == request.id
    assert (stored.kind, stored.reason, stored.read_at) == ("rejected", "card_unclear", None)
    assert stored.created_at == frozen_clock_now()
    # No column for a name, phone, number, address or note (FR-019).
    assert {c.key for c in inspect(Notification).columns} == {
        "id",
        "marketer_id",
        "request_id",
        "kind",
        "reason",
        "created_at",
        "read_at",
    }


def frozen_clock_now():
    from app.core.timeutil import utc_now

    return utc_now()


def test_add_does_not_commit(db, marketer) -> None:
    request = request_factory(db, marketer)
    notification_service.add(db, request, "approved")
    db.rollback()
    assert db.scalars(select(Notification)).all() == []


def test_unread_count_read_and_read_all(db, marketer, make_user) -> None:
    other = make_user("marketer")
    rows = [
        notification_service.add(db, request_factory(db, marketer), "approved") for _ in range(3)
    ]
    notification_service.add(db, request_factory(db, other), "approved")
    db.flush()
    assert notification_service.unread_count(db, marketer) == 3

    notification_service.mark_read(db, marketer, rows[0].id)
    first_read = db.get(Notification, rows[0].id).read_at
    assert first_read is not None
    assert notification_service.unread_count(db, marketer) == 2

    # Idempotent: the first read time stays.
    notification_service.mark_read(db, marketer, rows[0].id)
    assert db.get(Notification, rows[0].id).read_at == first_read

    notification_service.mark_all(db, marketer)
    assert notification_service.unread_count(db, marketer) == 0
    # Another marketer's rows are untouched.
    assert notification_service.unread_count(db, other) == 1


def test_mark_read_of_another_marketers_row_is_not_found(db, marketer, make_user) -> None:
    other = make_user("marketer")
    row = notification_service.add(db, request_factory(db, other), "approved")
    db.flush()
    with pytest.raises(AppError) as err:
        notification_service.mark_read(db, marketer, row.id)
    assert (err.value.code, err.value.status) == ("notification_not_found", 404)


def test_page_is_newest_first_with_next_before(db, marketer, frozen_clock) -> None:
    ids = []
    for _ in range(5):
        ids.append(notification_service.add(db, request_factory(db, marketer), "approved").id)
        frozen_clock.advance(timedelta(minutes=1))
    db.flush()

    first = notification_service.page(db, marketer, before=None, limit=2)
    assert [i.id for i in first.items] == [ids[4], ids[3]]
    assert first.next_before == ids[3]
    second = notification_service.page(db, marketer, before=first.next_before, limit=2)
    assert [i.id for i in second.items] == [ids[2], ids[1]]
    last = notification_service.page(db, marketer, before=second.next_before, limit=2)
    assert [i.id for i in last.items] == [ids[0]]
    assert last.next_before is None


def test_page_shows_the_name_live_and_labels_not_notes(db, marketer, make_user) -> None:
    admin = admin_with(make_user, "review", "delete")
    request = request_factory(
        db, marketer, status="rejected", rejection_reason="other", rejection_note="ملاحظة المراجع"
    )
    notification_service.add(db, request, "rejected", "other")
    db.flush()

    item = notification_service.page(db, marketer, before=None, limit=10).items[0]
    assert item.full_name == request.full_name
    assert item.number_label == request.number_label
    assert (item.kind, item.deleted, item.reason_label) == ("rejected", False, "سبب آخر")
    assert "ملاحظة المراجع" not in item.model_dump_json()

    # After a deletion (011) the same row shows no name.
    mark_deleted(db, request, admin, reason="duplicate")
    notification_service.add(db, request, "deleted", "duplicate")
    db.flush()
    deleted, rejected = notification_service.page(db, marketer, before=None, limit=10).items
    assert (rejected.full_name, rejected.deleted) == (None, True)
    assert (deleted.kind, deleted.full_name, deleted.reason_label) == ("deleted", None, "طلب مكرر")


def test_linked_and_unlinked_may_repeat(db, marketer) -> None:
    request = request_factory(db, marketer, status="linked")
    for kind, reason in (("linked", None), ("unlinked", "x"), ("linked", None)):
        notification_service.add(db, request, kind, reason)
    db.flush()
    kinds = [i.kind for i in notification_service.page(db, marketer, before=None, limit=10).items]
    assert kinds == ["linked", "unlinked", "linked"]
