"""The marketer never learns anything about the matched subscriber (specs/009 FR-012, SC-003).

Every path (return by identity, return by phone, conflict, second subscription, pending block,
contact-admin) is walked through the API, and every response body the marketer receives is
collected. None may hold the matched record's name, phone, username, tower, national ID or family
number (unless it is the marketer's own input), request number, draft id or source reference.
Synthetic data only.
"""

import uuid
from pathlib import Path

import pytest

from app.config import get_settings
from app.services.card_reader_fake_data import FAMILY, NID
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.requests import request_factory
from tests.helpers.submit import PHONE, complete_draft, make_catalog, marketer_headers

SECRET_NAME = "اسم مطابق سري جداً"
SECRET_USERNAME = "SECRETUSER-0001"
OTHER_PHONE = "07709990002"
OTHER_NID = "199077778888"
OTHER_FAMILY = "8888X0000000000008"


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    get_otp_sender().outbox.clear()
    return tmp_path


@pytest.fixture
def catalog(client, make_user):
    return make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))


@pytest.fixture
def h(client, make_user):
    return marketer_headers(client, make_user("marketer"))


class Seen:
    """Every response body the marketer got, as text."""

    def __init__(self, client, h):
        self.client, self.h, self.bodies = client, h, []

    def _keep(self, res):
        self.bodies.append(res.text)
        return res

    def get(self, path):
        return self._keep(self.client.get(path, headers=self.h))

    def post(self, path, **kw):
        return self._keep(self.client.post(path, headers=self.h, **kw))

    def patch(self, draft_id, changes):
        version = self.get(f"/api/drafts/{draft_id}").json()["version"]
        return self._keep(
            self.client.patch(
                f"/api/drafts/{draft_id}",
                json={"version": version, "changes": changes},
                headers=self.h,
            )
        )

    def verify_and_submit(self, draft_id):
        self.post(f"/api/drafts/{draft_id}/otp/send")
        outbox = get_otp_sender().outbox
        if outbox:
            self.post(f"/api/drafts/{draft_id}/otp/verify", json={"code": outbox[-1][1]})
        version = self.get(f"/api/drafts/{draft_id}").json()["version"]
        res = self.post(f"/api/drafts/{draft_id}/submit", json={"version": version})
        if res.status_code in (200, 201):
            self.get(f"/api/requests/{res.json()['id']}")
        self.get("/api/requests")
        self.get("/api/drafts")
        return res

    def assert_hides(self, record, *extra: str):
        blob = "\n".join(self.bodies)
        secrets = [
            record.full_name,
            record.username,
            record.tower_code,
            f"T3C-{record.number}",
            str(record.draft_id),
            '"matched_ref"',
            '"matched_source"',
            *extra,
        ]
        for secret in secrets:
            assert secret not in blob, secret


def _record(db, make_user, **values):
    return request_factory(
        db,
        make_user("marketer"),
        full_name=SECRET_NAME,
        username=SECRET_USERNAME,
        **values,
    )


def test_return_by_identity(client, db, h, catalog, make_user):
    old = _record(
        db,
        make_user,
        national_id=NID,
        national_id_input=NID,
        family_number=FAMILY,
        phone=OTHER_PHONE,
    )
    seen = Seen(client, h)
    draft_id = complete_draft(client, h, catalog, verified=False)
    seen.get(f"/api/drafts/{draft_id}")
    seen.patch(draft_id, {"return_chosen": True})
    assert seen.verify_and_submit(draft_id).status_code == 201
    seen.assert_hides(old, OTHER_PHONE)


def test_return_by_phone(client, db, h, catalog, make_user):
    old = _record(
        db,
        make_user,
        phone=PHONE,
        national_id=OTHER_NID,
        national_id_input=OTHER_NID,
        family_number=OTHER_FAMILY,
    )
    seen = Seen(client, h)
    draft_id = complete_draft(client, h, catalog, verified=False)
    seen.post(f"/api/drafts/{draft_id}/otp/send")  # refused, names no one
    seen.patch(draft_id, {"return_chosen": True})
    seen.post(f"/api/drafts/{draft_id}/contact-admin")
    assert seen.verify_and_submit(draft_id).status_code == 201
    seen.assert_hides(old, OTHER_NID, OTHER_FAMILY)


def test_conflict(client, db, h, catalog, make_user):
    old = _record(
        db,
        make_user,
        national_id=NID,
        national_id_input=NID,
        family_number=OTHER_FAMILY,
        phone=OTHER_PHONE,
    )
    seen = Seen(client, h)
    draft_id = complete_draft(client, h, catalog, verified=False)
    seen.get(f"/api/drafts/{draft_id}")
    assert seen.verify_and_submit(draft_id).status_code == 201
    seen.assert_hides(old, OTHER_FAMILY, OTHER_PHONE)


def test_second_subscription(client, db, h, catalog, make_user):
    old = _record(
        db,
        make_user,
        family_number=FAMILY,
        national_id=OTHER_NID,
        national_id_input=OTHER_NID,
        phone=OTHER_PHONE,
    )
    seen = Seen(client, h)
    draft_id = complete_draft(client, h, catalog, verified=False)
    seen.patch(draft_id, {"additional_confirmed": True})
    assert seen.verify_and_submit(draft_id).status_code == 201
    seen.assert_hides(old, OTHER_NID, OTHER_PHONE)


def test_pending_block(client, db, h, catalog, make_user):
    old = _record(
        db,
        make_user,
        status="pending_review",
        national_id=NID,
        national_id_input=NID,
        family_number=FAMILY,
        phone=OTHER_PHONE,
    )
    seen = Seen(client, h)
    draft_id = complete_draft(client, h, catalog, verified=False)
    seen.patch(draft_id, {"return_chosen": True})
    assert seen.verify_and_submit(draft_id).status_code == 409
    seen.assert_hides(old, OTHER_PHONE)


def test_the_test_catches_a_leak(client, db, h, make_user):
    """The check itself can fail: a body holding the name is caught."""
    old = _record(db, make_user)
    seen = Seen(client, h)
    seen.bodies.append(f'{{"name": "{SECRET_NAME}"}}')
    with pytest.raises(AssertionError):
        seen.assert_hides(old)
    assert uuid.UUID(str(old.draft_id))
