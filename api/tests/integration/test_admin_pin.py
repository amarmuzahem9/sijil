"""«تثبيت» of an edited national ID or family number (specs/010 US3: FR-013 to FR-015, FR-019a;
research R3 to R5). Synthetic data only."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.family_key import family_key
from app.models import AuditLog, Request, RequestNumberPin, RequestReason
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for, pending_request

NOW = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)
READ_NID = "199011112222"
READ_FAMILY = "2222B0000000000001"
MRZ_NID = "199011113333"


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.fixture
def reviewer(make_user):
    return admin_with(make_user, "review", name="أدمن التثبيت")


@pytest.fixture
def h(client, reviewer):
    return headers_for(client, reviewer)


def _pin(client, h, request_id, body):
    return client.post(f"/api/admin/requests/{request_id}/pin", json=body, headers=h)


def _edited(db, marketer, fields=("national_id", "family_number"), *, reading=True, **overrides):
    """A new pending request whose marketer edited `fields`; the card read READ_NID and
    READ_FAMILY (unless `reading` is False), and the MRZ gave MRZ_NID."""
    card_fields = (
        {
            "national_id": {"original": READ_NID, "edited": True},
            "family_number": {"original": READ_FAMILY, "edited": True},
        }
        if reading
        else {}
    )
    return pending_request(
        db,
        marketer,
        [("numbers_edited", None, {"fields": list(fields)})],
        card_fields=card_fields,
        **{"national_id_check": {"mrz": MRZ_NID}, **overrides},
    )


def _rows(db, request, reason=None):
    db.expire_all()
    query = select(RequestReason).where(RequestReason.request_id == request.id)
    if reason:
        query = query.where(RequestReason.reason == reason)
    return db.scalars(query.order_by(RequestReason.id)).all()


# --- sources ---


def test_pin_the_reading_family_number(client, db, h, reviewer, marketer, frozen_clock) -> None:
    frozen_clock.set(NOW)
    request = _edited(db, marketer, ["family_number"])
    before = request.family_number
    submitted = (request.submitted_national_id, request.submitted_family_number)
    card_fields = dict(request.card_fields)

    res = _pin(client, h, request.id, {"field": "family_number", "source": "reading"})

    assert res.status_code == 200, res.json()
    family = res.json()["numbers"]["family_number"]
    assert family["current"] == READ_FAMILY
    assert family["pins"] == [
        {
            "value": READ_FAMILY,
            "source": "reading",
            "by": "أدمن التثبيت",
            "at": "2026-11-23T09:00:00Z",
        }
    ]
    db.expire_all()
    request = db.get(Request, request.id)
    assert (request.family_number, request.family_key) == (READ_FAMILY, family_key(READ_FAMILY))
    assert (request.submitted_national_id, request.submitted_family_number) == submitted
    assert request.card_fields == card_fields
    (pin,) = db.scalars(select(RequestNumberPin).where(RequestNumberPin.request_id == request.id))
    assert (pin.field, pin.previous_value, pin.value, pin.source) == (
        "family_number",
        before,
        READ_FAMILY,
        "reading",
    )
    assert (pin.pinned_by, pin.pinned_at) == (reviewer.id, NOW)


def test_pin_the_mrz_national_id(client, db, h, marketer) -> None:
    request = _edited(db, marketer, ["national_id"])
    res = _pin(client, h, request.id, {"field": "national_id", "source": "mrz"})
    assert res.status_code == 200, res.json()
    db.expire_all()
    assert db.get(Request, request.id).national_id == MRZ_NID


def test_pin_the_marketer_value_after_another_pin(client, db, h, marketer) -> None:
    request = _edited(db, marketer, ["national_id"])
    marketer_value = request.submitted_national_id
    assert (
        _pin(client, h, request.id, {"field": "national_id", "source": "reading"}).status_code
        == 200
    )

    res = _pin(client, h, request.id, {"field": "national_id", "source": "marketer"})

    assert res.status_code == 200, res.json()
    db.expire_all()
    assert db.get(Request, request.id).national_id == marketer_value
    pins = db.scalars(
        select(RequestNumberPin)
        .where(RequestNumberPin.request_id == request.id)
        .order_by(RequestNumberPin.id)
    ).all()
    assert [(p.previous_value, p.value) for p in pins] == [
        (marketer_value, READ_NID),
        (READ_NID, marketer_value),
    ]


def test_typed_national_id_in_arabic_digits_is_normalized(client, db, h, marketer) -> None:
    request = _edited(db, marketer, ["national_id"])
    res = _pin(
        client,
        h,
        request.id,
        {"field": "national_id", "source": "typed", "value": " ١٩٩٠٤٤٤٤٥٥٥٥ "},
    )
    assert res.status_code == 200, res.json()
    db.expire_all()
    assert db.get(Request, request.id).national_id == "199044445555"


def test_typed_family_number_is_kept_as_written(client, db, h, marketer) -> None:
    request = _edited(db, marketer, ["family_number"])
    res = _pin(
        client,
        h,
        request.id,
        {"field": "family_number", "source": "typed", "value": "  2222b-0000000000009 "},
    )
    assert res.status_code == 200, res.json()
    db.expire_all()
    request = db.get(Request, request.id)
    assert request.family_number == "2222b-0000000000009"
    assert request.family_key == family_key("2222b-0000000000009")


@pytest.mark.parametrize(
    "body",
    [
        {"field": "national_id", "source": "reading", "value": "199099990000"},
        {"field": "family_number", "source": "mrz"},
        {"field": "family_number", "source": "typed"},
        {"field": "phone", "source": "reading"},
    ],
)
def test_bad_bodies_are_refused(client, db, h, marketer, body) -> None:
    request = _edited(db, marketer)
    res = _pin(client, h, request.id, body)
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"
    assert db.scalars(select(RequestNumberPin)).all() == []


def test_a_source_with_no_value(client, db, h, marketer) -> None:
    request = _edited(db, marketer, reading=False, national_id_check=None)
    for field, source in (("family_number", "reading"), ("national_id", "mrz")):
        res = _pin(client, h, request.id, {"field": field, "source": source})
        assert res.status_code == 422
        assert res.json()["code"] == "pin_source_empty"


# --- validation ---


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (
            {"field": "national_id", "source": "typed", "value": "19901111222"},
            "invalid_national_id",
        ),
        (
            {"field": "national_id", "source": "typed", "value": "1990-1111-2222"},
            "invalid_national_id",
        ),
        ({"field": "family_number", "source": "typed", "value": "-- //"}, "invalid_family_number"),
    ],
)
def test_typed_values_are_validated(client, db, h, marketer, body, code) -> None:
    request = _edited(db, marketer)
    res = _pin(client, h, request.id, body)
    assert res.status_code == 422
    assert res.json()["code"] == code
    assert db.scalars(select(RequestNumberPin)).all() == []


# --- the re-check (FR-014, FR-015) ---


def test_pin_to_an_existing_family(client, db, h, reviewer, marketer) -> None:
    old = request_factory(db, marketer, family_number=READ_FAMILY)
    request = _edited(db, marketer, ["family_number"])
    assert request.type == "new"

    res = _pin(client, h, request.id, {"field": "family_number", "source": "reading"})

    assert res.status_code == 200, res.json()
    body = res.json()
    assert body["type"] == "additional"
    assert body["warnings"] == []
    edited, family = _rows(db, request)
    assert (edited.reason, edited.state) == ("numbers_edited", "resolved")
    assert edited.state_changed_by == reviewer.id
    assert (family.reason, family.state, family.matched_ref) == (
        "family_exists",
        "open",
        str(old.id),
    )
    assert family.added_by == reviewer.id
    assert [r["state"] for r in body["reasons"]] == ["resolved", "open"]
    assert body["reasons"][1]["added_at_review"] is True


def test_numbers_edited_resolves_only_when_every_field_is_pinned(client, db, h, marketer) -> None:
    request = _edited(db, marketer)
    _pin(client, h, request.id, {"field": "family_number", "source": "reading"})
    assert _rows(db, request, "numbers_edited")[0].state == "open"
    _pin(client, h, request.id, {"field": "national_id", "source": "reading"})
    assert _rows(db, request, "numbers_edited")[0].state == "resolved"


def test_pin_away_and_back(client, db, h, reviewer, marketer) -> None:
    old = request_factory(db, marketer)
    # The submission matched old's family through the marketer's value.
    request = pending_request(
        db,
        marketer,
        [
            ("numbers_edited", None, {"fields": ["family_number"]}),
            ("family_exists", old, {}),
        ],
        type="additional",
        family_number=old.family_number,
        card_fields={"family_number": {"original": READ_FAMILY, "edited": True}},
    )

    _pin(client, h, request.id, {"field": "family_number", "source": "reading"})
    (family,) = _rows(db, request, "family_exists")
    assert family.state == "not_applicable"
    assert family.state_changed_by == reviewer.id
    assert db.get(Request, request.id).type == "additional"  # only new → additional

    res = _pin(client, h, request.id, {"field": "family_number", "source": "marketer"})
    assert res.status_code == 200, res.json()
    (family,) = _rows(db, request, "family_exists")
    assert family.state == "open"
    assert family.added_by is None  # the same row, reopened


def test_pin_never_changes_a_return_row(client, db, h, marketer) -> None:
    old = request_factory(db, marketer)
    request = pending_request(
        db,
        marketer,
        [
            ("return", old, {"basis": "identity"}),
            ("numbers_edited", None, {"fields": ["family_number"]}),
        ],
        type="return",
        national_id=old.national_id,
        national_id_input=old.national_id,
        family_number=old.family_number,
        card_fields={"family_number": {"original": READ_FAMILY, "edited": True}},
    )

    res = _pin(client, h, request.id, {"field": "family_number", "source": "reading"})

    assert res.status_code == 200, res.json()
    assert res.json()["type"] == "return"
    assert res.json()["warnings"] == ["return_target_lost"]
    (ret,) = _rows(db, request, "return")
    assert ret.state == "open"


# --- warnings (FR-019a) ---


def test_same_person_after_pins_needs_a_confirmed_accept(client, db, h, marketer) -> None:
    request_factory(
        db, marketer, national_id=READ_NID, national_id_input=READ_NID, family_number=READ_FAMILY
    )
    request = _edited(db, marketer)

    _pin(client, h, request.id, {"field": "family_number", "source": "reading"})
    res = _pin(client, h, request.id, {"field": "national_id", "source": "reading"})

    assert res.status_code == 200, res.json()
    assert res.json()["warnings"] == ["same_person"]

    res = client.post(f"/api/admin/requests/{request.id}/accept", json={}, headers=h)
    assert res.status_code == 409
    assert res.json()["code"] == "warnings_unconfirmed"
    assert res.json()["warnings"] == ["same_person"]

    res = client.post(
        f"/api/admin/requests/{request.id}/accept",
        json={"confirm_warnings": ["same_person"]},
        headers=h,
    )
    assert res.status_code == 200, res.json()
    assert res.json()["decision"]["despite_warnings"] == ["same_person"]
    db.expire_all()
    assert db.get(Request, request.id).approval_warnings == ["same_person"]
    (entry,) = db.scalars(select(AuditLog).where(AuditLog.action == "request.approved"))
    assert entry.after["despite_warnings"] == ["same_person"]


def test_a_new_id_conflict_warns(client, db, h, marketer) -> None:
    old = request_factory(db, marketer, national_id=READ_NID, national_id_input=READ_NID)
    request = _edited(db, marketer, ["national_id"])

    res = _pin(client, h, request.id, {"field": "national_id", "source": "reading"})

    assert res.status_code == 200, res.json()
    assert res.json()["warnings"] == ["id_conflict"]
    (conflict,) = _rows(db, request, "numbers_conflict")
    assert (conflict.state, conflict.matched_ref) == ("open", str(old.id))


# --- other ---


def test_a_decided_request_cannot_be_pinned(client, db, h, marketer) -> None:
    request = _edited(db, marketer)
    request.status = "approved"
    request.approved_at = request.submitted_at
    db.flush()
    res = _pin(client, h, request.id, {"field": "family_number", "source": "reading"})
    assert res.status_code == 409
    assert res.json()["code"] == "already_decided"


def test_without_review_is_404(client, db, make_user, marketer) -> None:
    request = _edited(db, marketer)
    other = headers_for(client, admin_with(make_user, "settings"))
    res = _pin(client, other, request.id, {"field": "family_number", "source": "reading"})
    assert res.status_code == 404
    assert res.json()["code"] == "request_not_found"
    res = _pin(
        client,
        headers_for(client, marketer),
        request.id,
        {"field": "family_number", "source": "reading"},
    )
    assert res.status_code == 404
