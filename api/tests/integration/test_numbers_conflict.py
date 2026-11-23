"""«تعارض بالأرقام» (specs/009 FR-004, owner's Q2): the national ID matches a subscriber whose
family number differs, or who has none. Sending is allowed and the request waits for review.

Synthetic data only: the fake card reader gives NID / FAMILY; existing subscribers come from the
request factory or a fake source.
"""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.core.matches import Matches, MatchRecord
from app.models import RequestReason
from app.services import match_service
from app.services.card_reader_fake_data import FAMILY, NID
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.requests import request_factory
from tests.helpers.submit import (
    complete_draft,
    get_draft,
    make_catalog,
    marketer_headers,
    patch,
    submit,
    verify,
)

OTHER_FAMILY = "5555B0000000000005"


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def fake_sender():
    sender = get_otp_sender()
    sender.outbox.clear()
    sender.fail_with = None
    yield sender
    sender.outbox.clear()


@pytest.fixture
def catalog(client, make_user):
    return make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))


@pytest.fixture
def h(client, make_user):
    return marketer_headers(client, make_user("marketer"))


def _reasons(db, request_id):
    rows = db.scalars(
        select(RequestReason)
        .where(RequestReason.request_id == request_id)
        .order_by(RequestReason.id)
    )
    return [(r.reason, r.matched_source, r.matched_ref) for r in rows]


def test_conflict_is_a_notice_not_a_missing_item(client, db, h, catalog, make_user):
    request_factory(
        db,
        make_user("marketer"),
        national_id=NID,
        national_id_input=NID,
        family_number=OTHER_FAMILY,
    )
    draft = get_draft(client, h, complete_draft(client, h, catalog))  # verified, nothing missing
    assert draft["checks"]["id_conflict"] is True
    assert draft["checks"]["national_id_exists"] is False
    assert draft["checks"]["return_available"] is False
    assert draft["missing"] == []


def test_conflict_goes_to_review(client, db, h, catalog, make_user):
    old = request_factory(
        db,
        make_user("marketer"),
        national_id=NID,
        national_id_input=NID,
        family_number=OTHER_FAMILY,
    )
    res = submit(client, h, complete_draft(client, h, catalog))
    assert res.status_code == 201, res.json()
    body = res.json()
    assert (body["type"], body["status"], body["result"]) == (
        "new",
        "pending_review",
        "pending_approval",
    )
    assert body["reasons"] == ["numbers_conflict"]
    assert _reasons(db, body["id"]) == [("numbers_conflict", "sijil", str(old.id))]


def test_conflict_with_a_confirmed_family_is_additional(client, db, h, catalog, make_user):
    conflict = request_factory(
        db,
        make_user("marketer"),
        national_id=NID,
        national_id_input=NID,
        family_number=OTHER_FAMILY,
    )
    relative = request_factory(db, make_user("marketer"), family_number=FAMILY)
    draft_id = complete_draft(client, h, catalog, verified=False)
    assert patch(client, h, draft_id, {"additional_confirmed": True})["checks"][
        "additional_confirmed"
    ]
    verify(client, h, draft_id)

    res = submit(client, h, draft_id)

    assert res.status_code == 201, res.json()
    body = res.json()
    assert (body["type"], body["result"]) == ("additional", "pending_family")
    assert body["reasons"] == ["numbers_conflict", "family_exists"]
    assert _reasons(db, body["id"]) == [
        ("numbers_conflict", "sijil", str(conflict.id)),
        ("family_exists", "sijil", str(relative.id)),
    ]


def test_a_record_with_no_family_number_is_a_conflict(client, db, h, catalog):
    def legacy(db, *, phone, national_id, family_key):
        if national_id == NID:
            return Matches([MatchRecord("legacy", "L1", national_id=True)])
        return Matches()

    match_service.register_source("legacy", legacy)
    try:
        draft_id = complete_draft(client, h, catalog)
        assert get_draft(client, h, draft_id)["checks"]["id_conflict"] is True
        res = submit(client, h, draft_id)
    finally:
        match_service.unregister_source("legacy")
    assert res.status_code == 201, res.json()
    assert _reasons(db, res.json()["id"]) == [("numbers_conflict", "legacy", "L1")]
