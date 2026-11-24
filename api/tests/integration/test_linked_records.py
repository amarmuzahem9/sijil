"""Linked records shown on the review file (specs/010 research R8)."""

import dataclasses
import uuid

from app.core.matches import MatchRef
from app.core.timeutil import utc_now
from app.models import RequestImage
from app.services import linked_records
from tests.helpers.requests import request_factory


def _image(db, request, side: str) -> RequestImage:
    image = RequestImage(
        id=uuid.uuid4(),
        request_id=request.id,
        side=side,
        file_name=f"{uuid.uuid4().hex}.jpg",
        size_bytes=1000,
        width=100,
        height=60,
        uploaded_by=request.marketer_id,
        created_at=utc_now(),
    )
    db.add(image)
    db.flush()
    return image


def test_sijil_record_resolves_with_its_fields(db, make_user) -> None:
    record = request_factory(db, make_user("marketer"), status="linked", phone="07801110001")
    front = _image(db, record, "front")
    ref = MatchRef("sijil", str(record.id))

    found = linked_records.resolve(db, [ref])

    out = found[ref]
    assert out.available is True
    assert (out.source, out.ref) == ("sijil", str(record.id))
    assert out.full_name == record.full_name
    assert out.username == record.username
    assert out.phone == "07801110001"
    assert (out.tower_code, out.tower_name) == (record.tower_code, record.tower_name)
    assert out.registered_at == record.submitted_at
    assert out.status == "linked"
    assert out.image_ids == [front.id]
    assert out.expiry is None


def test_missing_row_and_unknown_source_are_unavailable(db) -> None:
    gone = MatchRef("sijil", "999999")
    legacy = MatchRef("legacy", "12")

    found = linked_records.resolve(db, [gone, legacy])

    assert found[gone].available is False
    assert found[legacy].available is False
    assert found[legacy].source == "legacy"
    assert found[legacy].full_name is None


def test_registered_resolver_is_used(db) -> None:
    def fake(db, refs):
        return {r: linked_records.LinkedRecord(r.source, r.ref_id, True, "قديم") for r in refs}

    linked_records.register_resolver("legacy", fake)
    try:
        ref = MatchRef("legacy", "5")
        assert linked_records.resolve(db, [ref])[ref].full_name == "قديم"
    finally:
        linked_records.unregister_resolver("legacy")


def test_record_never_carries_card_data(db, make_user) -> None:
    record = request_factory(db, make_user("marketer"))
    ref = MatchRef("sijil", str(record.id))
    fields = {f.name for f in dataclasses.fields(linked_records.resolve(db, [ref])[ref])}
    assert not fields & {"card_readings", "national_id", "family_number", "card_fields"}


# --- specs/011 T041: a linked record that is a deleted request -------------------------------


def test_deleted_request_resolves_as_deleted_with_its_number_only(db, make_user) -> None:
    from tests.helpers.requests import mark_deleted
    from tests.helpers.review import admin_with

    old = request_factory(db, make_user("marketer"), status="pending_review")
    mark_deleted(db, old, admin_with(make_user, "review", "delete"))
    ref = MatchRef("sijil", str(old.id))

    record = linked_records.resolve(db, [ref])[ref]

    assert record == linked_records.LinkedRecord(
        source="sijil",
        ref=str(old.id),
        available=False,
        deleted=True,
        number_label=old.number_label,
    )


def test_live_record_is_not_deleted(db, make_user) -> None:
    old = request_factory(db, make_user("marketer"))
    ref = MatchRef("sijil", str(old.id))
    record = linked_records.resolve(db, [ref])[ref]
    assert record.available is True and record.deleted is False
    assert record.number_label == old.number_label


def test_reasons_of_another_request_stay_and_its_decision_works(client, db, make_user) -> None:
    """B keeps its reason when A is deleted; the file shows «سجل محذوف» data only; B can be
    accepted (FR-015)."""
    import json

    from tests.helpers.requests import mark_deleted
    from tests.helpers.review import admin_with, headers_for, pending_request

    marketer = make_user("marketer")
    reviewer = admin_with(make_user, "review", "delete")
    old = request_factory(db, marketer, status="pending_review", full_name="اسم المحذوف السري")
    phone = old.phone
    b = pending_request(db, marketer, [("family_exists", old, {})], type="additional")
    mark_deleted(db, old, reviewer)
    h = headers_for(client, reviewer)

    body = client.get(f"/api/admin/requests/{b.id}", headers=h).json()
    [reason] = body["reasons"]
    assert (reason["reason"], reason["state"]) == ("family_exists", "open")
    assert reason["record"]["deleted"] is True
    assert reason["record"]["number_label"] == old.number_label
    assert reason["record"]["available"] is False
    blob = json.dumps(body, ensure_ascii=False)
    assert "اسم المحذوف السري" not in blob and phone not in blob

    res = client.post(f"/api/admin/requests/{b.id}/accept", json={}, headers=h)
    assert res.status_code == 200, res.json()
    assert res.json()["type"] == "additional"
