"""A SAS subscriber in the review file (specs/015 US3: FR-015; research R13; contracts/api.md).
Review admins only; never notes, parent_name, a national ID, a family number or images.
Synthetic data only."""

import json
from datetime import UTC, date, datetime

import pytest

from app.core.matches import MatchRef
from app.models import RequestReason, SasImport, Tower
from app.services import linked_records
from tests.helpers.review import admin_with, headers_for, pending_request
from tests.helpers.sas import sas_subscriber, seed_towers

USERNAME = "ALM03-07811115555"


@pytest.fixture
def main_admin(make_user):
    return make_user("super_admin")


def _sas(db, admin, **values):
    towers = seed_towers(db)
    return sas_subscriber(
        db,
        admin,
        **(
            {
                "username": USERNAME,
                "full_name": "مشترك SAS للمراجعة",
                "phone": "07811115555",
                "tower_id": towers["ALM03"],
                # 2026-12-01 in Baghdad.
                "expires_at": datetime(2026, 11, 30, 21, 0, tzinfo=UTC),
                "sas_created_at": datetime(2025, 1, 10, 7, 0, tzinfo=UTC),
                "last_online_at": datetime(2026, 11, 20, 5, 0, tzinfo=UTC),
                "group_name": "PLUS",
                "parent_name": "PARENT-HIDDEN",
                "notes": "NOTE-HIDDEN",
            }
            | values
        ),
    )


def _linked_request(db, make_user, sub, reason="return"):
    request = pending_request(db, make_user("marketer"), [], type="return")
    db.add(
        RequestReason(
            request_id=request.id,
            reason=reason,
            matched_source="sas",
            matched_ref=str(sub.id),
            details={"basis": "phone"},
        )
    )
    db.flush()
    db.expire(request, ["reasons"])
    return request


def test_the_resolver_gives_the_sas_fields(db, main_admin) -> None:
    sub = _sas(db, main_admin)
    record = db.get(SasImport, sub.last_import_id)
    record.created_at = datetime(2026, 11, 24, 22, 30, tzinfo=UTC)  # 2026-11-25 in Baghdad
    tower = db.get(Tower, sub.tower_id)
    tower.name = "العلم الجديد"  # the current name is shown
    db.flush()
    ref = MatchRef("sas", str(sub.id))
    out = linked_records.resolve(db, [ref])[ref]
    assert out.available is True
    assert (out.source, out.ref) == ("sas", str(sub.id))
    assert (out.username, out.full_name, out.phone) == (
        USERNAME,
        "مشترك SAS للمراجعة",
        "07811115555",
    )
    assert out.username_phone is None  # equal to the phone column
    assert (out.tower_code, out.tower_name) == ("ALM03", "العلم الجديد")
    assert out.registered_at == datetime(2025, 1, 10, 7, 0, tzinfo=UTC)
    assert out.expiry == date(2026, 12, 1)
    assert out.expiry_as_of == date(2026, 11, 25)
    assert out.last_online == datetime(2026, 11, 20, 5, 0, tzinfo=UTC)
    assert out.group_name == "PLUS"
    assert out.missing_from_file is None
    assert out.image_ids == []
    assert (out.number_label, out.legacy_number, out.status) == (None, None, None)


def test_a_different_username_phone_and_the_missing_mark(db, main_admin) -> None:
    sub = _sas(
        db,
        main_admin,
        phone="07722226666",
        tower_id=None,
        missing_since=datetime(2026, 11, 26, 22, 0, tzinfo=UTC),  # 2026-11-27 in Baghdad
    )
    ref = MatchRef("sas", str(sub.id))
    out = linked_records.resolve(db, [ref])[ref]
    assert (out.phone, out.username_phone) == ("07722226666", "07811115555")
    assert (out.tower_code, out.tower_name) == (None, None)
    assert out.missing_from_file == date(2026, 11, 27)


def test_an_unknown_sas_ref_is_unavailable(db) -> None:
    ref = MatchRef("sas", "999999")
    out = linked_records.resolve(db, [ref])[ref]
    assert out.available is False
    assert out.username is None


def test_the_review_file_shows_the_sas_record(client, db, make_user, main_admin) -> None:
    sub = _sas(db, main_admin)
    request = _linked_request(db, make_user, sub)
    reviewer = admin_with(make_user, "review")
    res = client.get(f"/api/admin/requests/{request.id}", headers=headers_for(client, reviewer))
    assert res.status_code == 200, res.json()
    (reason,) = [r for r in res.json()["reasons"] if r["reason"] == "return"]
    assert reason["basis"] == "phone"
    record = reason["record"]
    assert record["source"] == "sas"
    assert record["available"] is True
    assert record["username"] == USERNAME
    assert record["tower_code"] == "ALM03"
    assert record["expiry"] == "2026-12-01"
    assert record["expiry_as_of"] is not None
    assert record["group_name"] == "PLUS"
    assert record["last_online"].startswith("2026-11-20")
    assert record["missing_from_file"] is None
    assert record["image_ids"] == []
    assert record["number_label"] is None  # never a request number
    text = json.dumps(res.json(), ensure_ascii=False)
    for hidden in ("PARENT-HIDDEN", "NOTE-HIDDEN"):
        assert hidden not in text


def test_a_marketer_never_sees_the_sas_record(client, db, make_user, main_admin) -> None:
    from tests.helpers.submit import marketer_headers

    sub = _sas(db, main_admin)
    marketer = make_user("marketer")
    request = pending_request(db, marketer, [], type="return")
    db.add(
        RequestReason(
            request_id=request.id,
            reason="return",
            matched_source="sas",
            matched_ref=str(sub.id),
            details={"basis": "phone"},
        )
    )
    db.flush()
    h = marketer_headers(client, marketer)
    admin_file = client.get(f"/api/admin/requests/{request.id}", headers=h)
    assert admin_file.status_code in (403, 404)
    own = client.get(f"/api/requests/{request.id}", headers=h)
    for hidden in (USERNAME, "مشترك SAS للمراجعة", "PLUS"):
        assert hidden not in own.text
