"""The check engine against Sijil requests (specs/008 FR-001, FR-002, FR-005; Q1).

Existing subscribers come from the synthetic request factory; nothing is real.
"""

import uuid

import pytest

from app.core.family_key import family_key
from app.core.national_id import normalize_national_id
from app.core.phone import normalize_phone
from app.models import Draft
from app.services import match_service
from tests.helpers.requests import request_factory

PHONE = "07801234567"
NID = "199011112222"
FAM = "1234A5678901234567"


def _find(db, phone=None, nid=None, fam=None):
    return match_service.find_matches(
        db,
        phone=normalize_phone(phone),
        national_id=normalize_national_id(nid),
        family_key=family_key(fam),
    )


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.mark.parametrize("status", ["pending_review", "approved", "linked"])
def test_active_statuses_match(db, marketer, status) -> None:
    req = request_factory(
        db,
        marketer,
        status=status,
        phone=PHONE,
        national_id=NID,
        national_id_input=NID,
        family_number=FAM,
    )
    m = _find(db, "+964 780 123 4567", "١٩٩٠١١١١٢٢٢٢", "1234 a 56789O1234567")
    ref = match_service.MatchRef("sijil", str(req.id))
    assert (m.phone, m.national_id, m.family) == ([ref], [ref], [ref])
    assert m.any


def test_rejected_requests_never_match(db, marketer) -> None:
    request_factory(
        db,
        marketer,
        status="rejected",
        phone=PHONE,
        national_id=NID,
        national_id_input=NID,
        family_number=FAM,
    )
    m = _find(db, PHONE, NID, FAM)
    assert (m.phone, m.national_id, m.family) == ([], [], [])
    assert not m.any


def test_a_request_rejected_in_review_no_longer_matches(client, db, marketer, make_user) -> None:
    """specs/010 T056 (§6.4): the numbers of a request rejected through «رفض» are free again."""
    from tests.helpers.review import headers_for

    req = request_factory(
        db,
        marketer,
        status="pending_review",
        phone=PHONE,
        national_id=NID,
        national_id_input=NID,
        family_number=FAM,
    )
    assert _find(db, PHONE, NID, FAM).any

    res = client.post(
        f"/api/admin/requests/{req.id}/reject",
        json={"reason": "card_unclear"},
        headers=headers_for(client, make_user("super_admin")),
    )
    assert res.status_code == 200, res.json()

    db.expire_all()
    m = _find(db, PHONE, NID, FAM)
    assert (m.phone, m.national_id, m.family) == ([], [], [])


def test_drafts_never_match(db, marketer, make_user) -> None:
    other = make_user("marketer")
    db.add(
        Draft(
            id=uuid.uuid4(),
            marketer_id=other.id,
            phone_input=PHONE,
            phone_normalized=PHONE,
            national_id=NID,
            family_number=FAM,
        )
    )
    db.flush()
    assert not _find(db, PHONE, NID, FAM).any


def test_missing_keys_are_never_queried(db, marketer) -> None:
    request_factory(db, marketer, phone=PHONE)
    m = _find(db, None, None, None)
    assert not m.any


def test_each_key_matches_on_its_own(db, marketer) -> None:
    req = request_factory(db, marketer, phone=PHONE)
    m = _find(db, PHONE, "199099998888", "9999Z0000000000000")
    assert m.phone == [match_service.MatchRef("sijil", str(req.id))]
    assert (m.national_id, m.family) == ([], [])


def test_several_family_matches_are_all_returned(db, marketer) -> None:
    a = request_factory(db, marketer, family_number=FAM)
    b = request_factory(db, marketer, family_number="1234a5678901234567")
    m = _find(db, fam=FAM)
    assert sorted(r.ref_id for r in m.family) == sorted([str(a.id), str(b.id)])


def test_registered_sources_are_asked(db) -> None:
    calls = []

    def source(db, *, phone, national_id, family_key):
        calls.append((phone, national_id, family_key))
        return match_service.Matches([match_service.MatchRecord("legacy", "x", phone=True)])

    match_service.register_source("legacy", source)
    try:
        m = _find(db, PHONE)
    finally:
        match_service.unregister_source("legacy")
    assert calls == [(PHONE, None, None)]
    assert m.phone == [match_service.MatchRef("legacy", "x")]


# --- one record per matching request, with its flags (specs/009 research R1) ---


def test_one_record_per_request_with_its_flags(db, marketer) -> None:
    same = request_factory(db, marketer, national_id=NID, national_id_input=NID, family_number=FAM)
    conflict = request_factory(
        db,
        marketer,
        national_id=NID,
        national_id_input=NID,
        family_number="5555B0000000000000",
    )
    relative = request_factory(db, marketer, family_number=FAM)
    phone_only = request_factory(db, marketer, phone=PHONE)
    m = _find(db, PHONE, NID, FAM)
    by_id = {r.ref_id: r for r in m.records}
    assert len(m.records) == 4
    assert (by_id[str(same.id)].national_id, by_id[str(same.id)].family) == (True, True)
    assert (by_id[str(conflict.id)].national_id, by_id[str(conflict.id)].family) == (True, False)
    assert (by_id[str(relative.id)].national_id, by_id[str(relative.id)].family) == (False, True)
    assert by_id[str(phone_only.id)].phone is True
    assert not by_id[str(phone_only.id)].national_id
    assert [r.ref_id for r in m.same_person] == [str(same.id)]
    assert [r.ref_id for r in m.id_conflict] == [str(conflict.id)]
    assert [r.ref_id for r in m.family_only] == [str(relative.id)]


@pytest.mark.parametrize(("status", "pending"), [("pending_review", True), ("approved", False)])
def test_pending_flag(db, marketer, status, pending) -> None:
    request_factory(db, marketer, status=status, phone=PHONE)
    (record,) = _find(db, PHONE).records
    assert record.pending is pending


def test_one_query_per_lookup(db, marketer) -> None:
    from sqlalchemy import event

    request_factory(db, marketer, phone=PHONE, national_id=NID, national_id_input=NID)
    statements = []

    def count(conn, cursor, statement, *args):
        if "FROM requests" in statement:
            statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", count)
    try:
        _find(db, PHONE, NID, FAM)
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert len(statements) == 1
