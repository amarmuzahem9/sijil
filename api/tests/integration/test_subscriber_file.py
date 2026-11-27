"""The subscriber's file (docs/system.md v1.24 §10 item 4; specs/018 US2, FR-007, FR-008, FR-011;
research R5–R9; contracts/api.md). One record, its linked records with their reasons, the request
history. Synthetic data only."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import ImageAccessLog, RequestLink
from tests.helpers.legacy import legacy_subscriber
from tests.helpers.requests import add_images, add_pin, mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for
from tests.helpers.sas import sas_subscriber

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
PHONE, OTHER_PHONE = "07816660001", "07816660002"
NID = "199066600001"
FAMILY = "1990F6660000000001"


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def reviewer(make_user):
    return admin_with(make_user, "review", name="مراجع تجريبي")


@pytest.fixture
def marketer(make_user):
    return make_user("marketer", name="مسوّق ملف تجريبي")


def _file(client, user, source, ref):
    res = client.get(f"/api/admin/subscribers/{source}/{ref}", headers=headers_for(client, user))
    assert res.status_code == 200, res.json()
    return res.json()


def _linked(body) -> dict[tuple[str, str], str]:
    return {(x["row"]["source"], x["row"]["ref"]): x["reason"] for x in body["linked"]}


@pytest.fixture
def person(db, marketer, reviewer):
    """A request; an older rejected request of the same person; a SAS row with its phone; a legacy
    row with its family number; a «ملغي» legacy row with its phone; a stranger."""
    request = request_factory(
        db,
        marketer,
        status="approved",
        phone=PHONE,
        national_id=NID,
        national_id_input=NID,
        family_number=FAMILY,
        submitted_at=T0,
    )
    older = request_factory(
        db,
        marketer,
        status="rejected",
        approved_at=None,
        phone=OTHER_PHONE,
        national_id=NID,
        national_id_input=NID,
        family_number=FAMILY,
        submitted_at=T0 - timedelta(days=60),
    )
    sas = sas_subscriber(db, reviewer, username=f"ZZF01-{PHONE}", phone=PHONE)
    family = legacy_subscriber(db, reviewer, family_number="1990 f 6660000000001")
    cancelled = legacy_subscriber(db, reviewer, phone=PHONE, status_text="ملغي")
    stranger = request_factory(db, marketer, status="approved")
    return locals()


# --- linked records (FR-007, research R5) --------------------------------------------------------


def test_linked_records_and_their_reasons(client, person, reviewer) -> None:
    body = _file(client, reviewer, "sijil", person["request"].id)
    assert _linked(body) == {
        ("sijil", str(person["older"].id)): "same_person",
        ("sas", str(person["sas"].id)): "same_phone",
        ("legacy", str(person["family"].id)): "same_family",
        ("legacy", str(person["cancelled"].id)): "same_phone",
    }
    assert body["more_linked"] == 0
    assert ("sijil", str(person["stranger"].id)) not in _linked(body)
    assert ("sijil", str(person["request"].id)) not in _linked(body)  # never itself


def test_the_strongest_reason_wins(client, db, person, reviewer, marketer) -> None:
    # Same person and same phone at once: «نفس الشخص».
    twin = request_factory(
        db,
        marketer,
        status="rejected",
        approved_at=None,
        phone=PHONE,
        national_id=NID,
        national_id_input=NID,
        family_number=FAMILY,
    )
    assert (
        _linked(_file(client, reviewer, "sijil", person["request"].id))[("sijil", str(twin.id))]
        == "same_person"
    )


def test_from_a_sas_row_and_from_a_legacy_row(client, person, reviewer) -> None:
    from_sas = _linked(_file(client, reviewer, "sas", person["sas"].id))
    assert from_sas[("sijil", str(person["request"].id))] == "same_phone"
    assert from_sas[("legacy", str(person["cancelled"].id))] == "same_phone"
    from_legacy = _linked(_file(client, reviewer, "legacy", person["family"].id))
    assert from_legacy[("sijil", str(person["request"].id))] == "same_family"
    assert from_legacy[("sijil", str(person["older"].id))] == "same_family"


def test_at_most_50_linked(client, db, reviewer) -> None:
    clan = "1990C6660000000009"
    first = legacy_subscriber(db, reviewer, family_number=clan)
    for _ in range(55):
        legacy_subscriber(db, reviewer, family_number=clan)
    body = _file(client, reviewer, "legacy", first.id)
    assert (len(body["linked"]), body["more_linked"]) == (50, 5)


@pytest.mark.parametrize(("source", "ref"), [("sijil", 999999999), ("legacy", 0), ("sas", -1)])
def test_unknown_record(client, reviewer, source, ref) -> None:
    res = client.get(
        f"/api/admin/subscribers/{source}/{ref}", headers=headers_for(client, reviewer)
    )
    assert (res.status_code, res.json()["code"]) == (404, "not_found")


def test_unknown_source(client, reviewer) -> None:
    res = client.get("/api/admin/subscribers/other/1", headers=headers_for(client, reviewer))
    assert res.status_code in (404, 422)


# --- history (FR-008, research R9) ---------------------------------------------------------------


def test_request_history_in_order(client, db, person, reviewer, make_user) -> None:
    request = person["request"]
    accepter = admin_with(make_user, "review", name="قابل تجريبي")
    linker = admin_with(make_user, "link", name="رابط تجريبي")
    request.approved_at, request.approved_by = T0 + timedelta(hours=1), accepter.id
    pin = add_pin(db, request, reviewer)
    pin.pinned_at = T0 + timedelta(minutes=30)
    request.status, request.linked_at, request.linked_by = "approved", None, None
    for i, (kind, reason) in enumerate([("linked", None), ("unlinked", "by_mistake")]):
        db.add(
            RequestLink(
                request_id=request.id,
                kind=kind,
                actor_id=linker.id,
                at=T0 + timedelta(hours=2 + i),
                reason=reason,
            )
        )
    db.flush()

    history = _file(client, reviewer, "sijil", request.id)["history"]
    assert [h["kind"] for h in history] == ["submitted", "pinned", "approved", "linked", "unlinked"]
    submitted, pinned, approved, linked, unlinked = history
    assert submitted["by_name"] == "مسوّق ملف تجريبي"
    assert (pinned["by_name"], pinned["field"]) == ("مراجع تجريبي", "national_id")
    assert "199000000099" not in str(pinned) and NID not in str(history)
    assert approved["by_name"] == "قابل تجريبي"
    assert linked["by_name"] == "رابط تجريبي"
    assert unlinked["reason"] == "by_mistake"


def test_automatic_acceptance_and_rejection(client, person, reviewer) -> None:
    approved = _file(client, reviewer, "sijil", person["stranger"].id)["history"][1]
    assert (approved["kind"], approved["by_name"]) == ("approved", None)
    rejected = _file(client, reviewer, "sijil", person["older"].id)["history"][1]
    assert (rejected["kind"], rejected["reason"]) == ("rejected", "card_unclear")


# --- record fields per source (FR-008) -----------------------------------------------------------


def test_request_record_for_review(client, db, uploads, person, reviewer) -> None:
    request = person["request"]
    images = add_images(db, request, uploads)
    record = _file(client, reviewer, "sijil", request.id)["record"]
    assert (record["source"], record["ref"], record["number_label"]) == (
        "sijil",
        str(request.id),
        request.number_label,
    )
    assert (record["phone"], record["username"], record["status"], record["type"]) == (
        PHONE,
        request.username,
        "approved",
        "new",
    )
    assert record["marketer_name"] == "مسوّق ملف تجريبي"
    assert (record["national_id"], record["family_number"]) == (NID, FAMILY)
    assert set(record["card_fields"]) == {
        "birth_date",
        "issue_date",
        "expiry_date",
        "birth_place",
        "issuing_authority",
    }
    assert {i["id"] for i in record["images"]} == {str(i.id) for i in images}
    assert record["deleted"] is False


def test_legacy_record(client, db, person, reviewer) -> None:
    row = legacy_subscriber(
        db,
        reviewer,
        phone="07816660009",
        incomplete=True,
        extra={"mother_name": "عينة", "email": "x@example.invalid"},
    )
    record = _file(client, reviewer, "legacy", row.id)["record"]
    assert (record["legacy_number"], record["status_text"], record["incomplete"]) == (
        row.legacy_number,
        "تم",
        True,
    )
    assert record["counts_in_check"] is True
    assert record["extra"]["mother_name"] == "عينة"
    assert "email" not in record["extra"]  # never the e-mails (014 R12)


def test_sas_record(client, db, reviewer) -> None:
    row = sas_subscriber(
        db,
        reviewer,
        username="ZZS01-07816660010",
        phone="07816660011",
        expires_at=datetime(2026, 12, 1, tzinfo=UTC),
        group_name="PLUS",
        last_online_at=T0,
        missing_since=T0,
    )
    record = _file(client, reviewer, "sas", row.id)["record"]
    assert record["username"] == "ZZS01-07816660010"
    assert record["username_phone"] == "07816660010"
    assert record["group_name"] == "PLUS"
    assert record["expires_at"].startswith("2026-12-01")
    assert record["missing_since"] is not None and record["last_online_at"] is not None
    assert record["no_documents"] is True


def test_deleted_request_file(client, db, marketer, reviewer) -> None:
    request = request_factory(db, marketer, status="pending_review", approved_at=None)
    mark_deleted(db, request, reviewer)
    body = _file(client, reviewer, "sijil", request.id)
    record = body["record"]
    assert record["deleted"] is True
    assert record["number_label"] == request.number_label
    assert record["full_name"] is None and record["phone"] is None
    assert "national_id" not in record and "images" not in record
    assert body["linked"] == []
    assert body["history"][-1]["kind"] == "deleted"


# --- images open through the logged routes (FR-011) ----------------------------------------------


def test_opening_an_image_from_the_file_is_logged(client, db, uploads, person, reviewer) -> None:
    request = person["request"]
    add_images(db, request, uploads)
    record = _file(client, reviewer, "sijil", request.id)["record"]
    image_id = record["images"][0]["id"]
    res = client.get(f"/api/admin/request-images/{image_id}", headers=headers_for(client, reviewer))
    assert res.status_code == 200
    row = db.scalar(select(ImageAccessLog).where(ImageAccessLog.request_id == request.id))
    assert (row.user_id, str(row.image_id)) == (reviewer.id, image_id)
