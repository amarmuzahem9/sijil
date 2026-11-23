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
        return match_service.Matches(phone=[match_service.MatchRef("legacy", "x")])

    match_service.register_source("legacy", source)
    try:
        m = _find(db, PHONE)
    finally:
        match_service.unregister_source("legacy")
    assert calls == [(PHONE, None, None)]
    assert m.phone == [match_service.MatchRef("legacy", "x")]
