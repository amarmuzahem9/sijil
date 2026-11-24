"""A legacy subscriber in the review file (specs/014 US3: FR-015; research R12; contracts/api.md).
Review admins only; never the family number; e-mails stored but not shown. Synthetic data only."""

import json
import uuid
from datetime import UTC, datetime

import pytest

from app.core.matches import MatchRef
from app.models import LegacyImage, RequestReason
from app.services import linked_records
from tests.helpers.legacy import legacy_subscriber
from tests.helpers.review import admin_with, headers_for, pending_request

FAMILY = "4444D0000000000004"
STAMP = datetime(2024, 5, 3, 7, 0, tzinfo=UTC)


@pytest.fixture
def main_admin(make_user):
    return make_user("super_admin")


def _legacy(db, admin, **values):
    sub = legacy_subscriber(
        db,
        admin,
        legacy_number="T3C-042",
        full_name="مشترك قديم للمراجعة",
        phone="07811114242",
        family_number=FAMILY,
        form_submitted_at=STAMP,
        status_text="تم",
        extra={
            "mother_name": "عينة",
            "mother_father_name": "مثال",
            "birth_date": "1990/01/10",
            "email_1": "legacy@example.com",
            "email_2": "other@example.com",
        },
        **values,
    )
    return sub


def _image(db, sub, side) -> LegacyImage:
    image = LegacyImage(
        id=uuid.uuid4(),
        legacy_subscriber_id=sub.id,
        side=side,
        file_name=f"{uuid.uuid4().hex}.jpg",
        size_bytes=1000,
        width=100,
        height=60,
    )
    db.add(image)
    db.flush()
    return image


def _linked_request(db, make_user, sub, reason="family_exists"):
    request = pending_request(db, make_user("marketer"), [])
    db.add(
        RequestReason(
            request_id=request.id,
            reason=reason,
            matched_source="legacy",
            matched_ref=str(sub.id),
            details={"basis": "phone"} if reason == "return" else {},
        )
    )
    db.flush()
    db.expire(request, ["reasons"])
    return request


def test_the_resolver_gives_the_legacy_fields(db, main_admin) -> None:
    sub = _legacy(db, main_admin)
    back = _image(db, sub, "back")
    front = _image(db, sub, "front")
    ref = MatchRef("legacy", str(sub.id))
    out = linked_records.resolve(db, [ref])[ref]
    assert out.available is True
    assert (out.source, out.ref) == ("legacy", str(sub.id))
    assert out.legacy_number == "T3C-042"
    assert out.full_name == "مشترك قديم للمراجعة"
    assert out.phone == "07811114242"
    assert out.registered_at == STAMP
    assert out.status == "تم"
    assert out.incomplete is False
    assert out.extra == {
        "mother_name": "عينة",
        "mother_father_name": "مثال",
        "birth_date": "1990/01/10",
    }
    assert out.image_ids == [front.id, back.id]  # front first
    assert (out.username, out.tower_code, out.tower_name) == (None, None, None)


def test_an_unknown_legacy_ref_is_unavailable(db) -> None:
    ref = MatchRef("legacy", "999999")
    out = linked_records.resolve(db, [ref])[ref]
    assert out.available is False
    assert out.legacy_number is None


def test_the_review_file_shows_the_legacy_record(client, db, make_user, main_admin) -> None:
    sub = _legacy(db, main_admin, incomplete=True)
    _image(db, sub, "front")
    request = _linked_request(db, make_user, sub)
    reviewer = admin_with(make_user, "review")
    res = client.get(f"/api/admin/requests/{request.id}", headers=headers_for(client, reviewer))
    assert res.status_code == 200, res.json()
    (reason,) = [r for r in res.json()["reasons"] if r["reason"] == "family_exists"]
    record = reason["record"]
    assert record["source"] == "legacy"
    assert record["available"] is True
    assert record["legacy_number"] == "T3C-042"
    assert record["full_name"] == "مشترك قديم للمراجعة"
    assert record["status"] == "تم"
    assert record["incomplete"] is True
    assert record["extra"]["mother_name"] == "عينة"
    assert len(record["image_ids"]) == 1
    assert record["number_label"] is None  # never a request number
    text = json.dumps(res.json(), ensure_ascii=False)
    for hidden in (FAMILY, "legacy@example.com", "other@example.com"):
        assert hidden not in text


def test_a_return_by_phone_shows_the_legacy_record_too(client, db, make_user, main_admin) -> None:
    sub = _legacy(db, main_admin)
    request = _linked_request(db, make_user, sub, reason="return")
    res = client.get(
        f"/api/admin/requests/{request.id}",
        headers=headers_for(client, admin_with(make_user, "review")),
    )
    (reason,) = [r for r in res.json()["reasons"] if r["reason"] == "return"]
    assert (reason["basis"], reason["record"]["legacy_number"]) == ("phone", "T3C-042")


def test_sijil_records_carry_no_legacy_fields(client, db, make_user) -> None:
    from tests.helpers.requests import request_factory

    old = request_factory(db, make_user("marketer"))
    ref = MatchRef("sijil", str(old.id))
    out = linked_records.resolve(db, [ref])[ref]
    assert (out.legacy_number, out.incomplete, out.extra) == (None, None, None)
