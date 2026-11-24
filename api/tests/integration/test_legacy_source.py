"""The check engine against imported legacy subscribers (specs/014 US2: FR-011, FR-012, FR-021;
research R2, R3). Phone and family number only; never national ID; never pending.
Synthetic data only."""

import pytest

from app.core.family_key import family_key
from app.core.national_id import normalize_national_id
from app.core.phone import normalize_phone
from app.services import match_service
from tests.helpers.legacy import legacy_subscriber

PHONE = "07801239999"
NID = "199011119999"
FAM = "9999A0000000000009"


@pytest.fixture
def admin(make_user):
    return make_user("super_admin")


def _find(db, phone=None, nid=None, fam=None):
    return match_service.find_matches(
        db,
        phone=normalize_phone(phone),
        national_id=normalize_national_id(nid),
        family_key=family_key(fam),
    )


def _legacy_records(matches):
    return [r for r in matches.records if r.source == "legacy"]


def test_a_legacy_phone_matches(db, admin) -> None:
    sub = legacy_subscriber(db, admin, phone=PHONE)
    (record,) = _legacy_records(_find(db, phone="+964 780 123 9999"))
    assert (record.source, record.ref_id) == ("legacy", str(sub.id))
    assert (record.phone, record.family, record.national_id, record.pending) == (
        True,
        False,
        False,
        False,
    )


def test_a_legacy_family_number_matches_by_its_key(db, admin) -> None:
    sub = legacy_subscriber(db, admin, family_number="9999a 00000000000o9")
    matches = _find(db, fam=FAM)
    (record,) = _legacy_records(matches)
    assert record.ref_id == str(sub.id)
    assert (record.family, record.phone, record.national_id) == (True, False, False)
    # Family without national ID: the §6.1 case-3 view.
    assert [r.ref_id for r in matches.family_only if r.source == "legacy"] == [str(sub.id)]


def test_phone_and_family_on_one_record_give_one_match(db, admin) -> None:
    sub = legacy_subscriber(db, admin, phone=PHONE, family_number=FAM)
    (record,) = _legacy_records(_find(db, phone=PHONE, nid=NID, fam=FAM))
    assert record.ref_id == str(sub.id)
    assert (record.phone, record.family, record.national_id) == (True, True, False)


def test_a_national_id_alone_never_matches_a_legacy_subscriber(db, admin) -> None:
    legacy_subscriber(db, admin, phone=PHONE, family_number=FAM)
    assert _legacy_records(_find(db, nid=NID)) == []


@pytest.mark.parametrize("status", ["ملغي", "مرفوض"])
def test_cancelled_or_refused_legacy_rows_never_match(db, admin, status) -> None:
    legacy_subscriber(db, admin, phone=PHONE, family_number=FAM, status_text=status)
    assert _legacy_records(_find(db, phone=PHONE, fam=FAM)) == []


def test_a_legacy_row_without_keys_matches_nothing(db, admin) -> None:
    legacy_subscriber(db, admin)  # no phone, no family number
    assert _find(db).records == []
    assert _legacy_records(_find(db, phone=PHONE, fam=FAM)) == []


def test_legacy_records_come_with_sijil_records(db, admin, make_user) -> None:
    from tests.helpers.requests import request_factory

    req = request_factory(db, make_user("marketer"), phone=PHONE)
    sub = legacy_subscriber(db, admin, phone=PHONE)
    refs = {(r.source, r.ref_id) for r in _find(db, phone=PHONE).records}
    assert refs == {("sijil", str(req.id)), ("legacy", str(sub.id))}
