"""The count rule of a marketer month (docs/system.md v1.23 §9, specs/017 research R2).

counted = linked now, current link in the Baghdad month, not deleted, counted for commission, not in
any payment; without_commission = a return accepted with «لا»; paid_before = already in a payment.
"""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import RequestLink
from app.services import commission_service
from app.services.commission_service import MonthSplit
from tests.helpers.legacy import legacy_subscriber
from tests.helpers.requests import link_request, mark_deleted, pay_month, request_factory
from tests.helpers.review import admin_with
from tests.helpers.sas import sas_subscriber

OCT = date(2026, 10, 1)
NOV = date(2026, 11, 1)
# Baghdad is UTC+3: the last second of October and the first of November, in UTC.
OCT_LAST = datetime(2026, 10, 31, 20, 59, 59, tzinfo=UTC)
NOV_FIRST = datetime(2026, 10, 31, 21, 0, 0, tzinfo=UTC)
MID_OCT = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
MID_NOV = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.fixture
def linker(make_user):
    return admin_with(make_user, "link")


def _linked(db, marketer, at=MID_OCT, **over):
    return request_factory(db, marketer, status="linked", linked_at=at, **over)


def _undo(db, request, admin, at):
    request.status = "approved"
    request.linked_at = None
    request.linked_by = None
    db.add(
        RequestLink(
            request_id=request.id, kind="unlinked", actor_id=admin.id, at=at, reason="by_mistake"
        )
    )
    db.flush()


def _split(db, month, marketer) -> MonthSplit:
    return commission_service.month_split(db, month).get(marketer.id, MonthSplit(0, 0, 0))


def test_only_linked_requests_count(db, marketer, linker) -> None:
    request_factory(db, marketer, status="pending_review", approved_at=None)
    request_factory(db, marketer, status="rejected", approved_at=None)
    request_factory(db, marketer, status="approved")
    assert commission_service.month_split(db, OCT) == {}
    _linked(db, marketer)
    assert _split(db, OCT, marketer) == MonthSplit(counted=1, without_commission=0, paid_before=0)


def test_types_and_the_commission_answer(db, marketer) -> None:
    _linked(db, marketer, type="new")
    _linked(db, marketer, type="additional")
    _linked(db, marketer, type="return", counts_commission=True)
    _linked(db, marketer, type="return", counts_commission=False)
    assert _split(db, OCT, marketer) == MonthSplit(counted=3, without_commission=1, paid_before=0)


def test_deleted_requests_never_count(db, marketer, linker) -> None:
    for status in ("pending_review", "rejected"):
        mark_deleted(db, request_factory(db, marketer, status=status, approved_at=None), linker)
    assert commission_service.month_split(db, OCT) == {}
    # The 011 check: a linked request can never carry a deletion mark.
    with pytest.raises(IntegrityError), db.begin_nested():
        _linked(db, marketer, deleted_at=MID_OCT, deleted_by=linker.id, deletion_reason="test")


def test_legacy_and_sas_subscribers_never_count(db, marketer, linker) -> None:
    request = _linked(db, marketer)
    before = commission_service.month_split(db, OCT)
    legacy_subscriber(db, linker, phone=request.phone, family_number=request.family_number)
    sas_subscriber(db, linker, username=request.username, phone=request.phone)
    assert commission_service.month_split(db, OCT) == before
    assert set(before) == {marketer.id}


def test_baghdad_month_boundaries(db, marketer) -> None:
    _linked(db, marketer, at=OCT_LAST)
    _linked(db, marketer, at=NOV_FIRST)
    assert _split(db, OCT, marketer).counted == 1
    assert _split(db, NOV, marketer).counted == 1


def test_undo_and_relink_count_once_in_the_new_month(db, marketer, linker) -> None:
    request = _linked(db, marketer)
    _undo(db, request, linker, MID_NOV)
    assert commission_service.month_split(db, OCT) == {}
    assert commission_service.month_split(db, NOV) == {}
    link_request(db, request, linker, at=MID_NOV)
    assert commission_service.month_split(db, OCT) == {}
    assert _split(db, NOV, marketer).counted == 1


def test_a_paid_request_never_counts_again(db, marketer, linker) -> None:
    """Owner Q1: paid in October, undone and linked again in November → not counted."""
    request = _linked(db, marketer)
    other = _linked(db, marketer)
    pay_month(db, marketer, OCT, linker, [request, other], rate=5000)
    _undo(db, request, linker, MID_NOV)
    link_request(db, request, linker, at=MID_NOV)
    assert _split(db, NOV, marketer) == MonthSplit(counted=0, without_commission=0, paid_before=1)


def test_archived_marketer_still_counts(db, marketer, linker) -> None:
    _linked(db, marketer)
    marketer.archived_at = MID_NOV
    marketer.archived_by = linker.id
    marketer.is_active = False
    db.flush()
    assert _split(db, OCT, marketer).counted == 1


def test_filter_by_marketer(db, marketer, make_user) -> None:
    other = make_user("marketer")
    _linked(db, marketer)
    _linked(db, other)
    assert set(commission_service.month_split(db, OCT)) == {marketer.id, other.id}
    assert set(commission_service.month_split(db, OCT, [other.id])) == {other.id}
