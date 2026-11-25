"""The check engine against imported SAS subscribers (specs/015 US2: FR-011, FR-012, FR-022;
research R8). Phone only, through the phone column or the phone inside the username; never
national ID or family number; never pending; rows missing from the last file still count.
Synthetic data only."""

import pytest

from app.core.family_key import family_key
from app.core.national_id import normalize_national_id
from app.core.phone import normalize_phone
from app.core.timeutil import utc_now
from app.services import match_service
from tests.helpers.requests import request_factory
from tests.helpers.sas import sas_subscriber

PHONE = "07801238888"
OTHER = "07701238888"
NID = "199011118888"
FAM = "8888A0000000000008"


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


def _sas(matches):
    return [r for r in matches.records if r.source == "sas"]


def test_the_phone_column_matches(db, admin) -> None:
    sub = sas_subscriber(db, admin, username="ZZT01-07709990000", phone=PHONE)
    (record,) = _sas(_find(db, phone="+964 780 123 8888"))
    assert (record.source, record.ref_id) == ("sas", str(sub.id))
    assert (record.phone, record.national_id, record.family, record.pending) == (
        True,
        False,
        False,
        False,
    )


def test_the_phone_inside_the_username_matches(db, admin) -> None:
    sub = sas_subscriber(db, admin, username=f"RBD-01S-{PHONE}", phone=None)
    (record,) = _sas(_find(db, phone=PHONE))
    assert record.ref_id == str(sub.id)
    assert record.phone is True
    assert [r.ref_id for r in _find(db, phone=PHONE).phone_records] == [str(sub.id)]


def test_two_different_phones_both_match_the_same_record(db, admin) -> None:
    sub = sas_subscriber(db, admin, username=f"KZF06-{PHONE}", phone=OTHER)
    assert [r.ref_id for r in _sas(_find(db, phone=PHONE))] == [str(sub.id)]
    assert [r.ref_id for r in _sas(_find(db, phone=OTHER))] == [str(sub.id)]


def test_equal_phones_give_one_record(db, admin) -> None:
    sas_subscriber(db, admin, username=f"ALM03-{PHONE}", phone=PHONE)
    assert len(_sas(_find(db, phone=PHONE))) == 1


def test_national_id_and_family_number_never_match_a_sas_subscriber(db, admin) -> None:
    sas_subscriber(db, admin, username=f"ALM03-{PHONE}", phone=PHONE)
    assert _sas(_find(db, nid=NID, fam=FAM)) == []
    (record,) = _sas(_find(db, phone=PHONE, nid=NID, fam=FAM))
    assert (record.national_id, record.family) == (False, False)


def test_a_row_missing_from_the_last_file_still_matches(db, admin) -> None:
    sub = sas_subscriber(db, admin, username=f"ALM03-{PHONE}", phone=PHONE)
    sub.missing_since = utc_now()
    db.flush()
    assert [r.ref_id for r in _sas(_find(db, phone=PHONE))] == [str(sub.id)]


def test_a_row_without_phones_matches_nothing(db, admin) -> None:
    sas_subscriber(db, admin, username="LEGACYUSER", phone=None)
    assert _sas(_find(db, phone=PHONE)) == []
    assert _sas(_find(db)) == []


def test_sas_records_come_with_sijil_records(db, admin, make_user) -> None:
    request = request_factory(db, make_user("marketer"), phone=PHONE)
    sub = sas_subscriber(db, admin, username=f"ALM03-{PHONE}", phone=PHONE)
    refs = {(r.source, r.ref_id) for r in _find(db, phone=PHONE).phone_records}
    assert refs == {("sijil", str(request.id)), ("sas", str(sub.id))}
