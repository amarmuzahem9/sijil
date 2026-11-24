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


# --- after the admin's decision (specs/010 T028, FR-011, SC-004) ---------------------------------

ADMIN_NAME = "أدمن سري للمراجعة"


@pytest.mark.parametrize("action", ["accept", "reject"])
def test_decision_shows_nothing_of_the_linked_record(client, db, h, catalog, make_user, action):
    old = _record(db, make_user, family_number=FAMILY, national_id=OTHER_NID, phone=OTHER_PHONE)
    seen = Seen(client, h)
    draft_id = complete_draft(client, h, catalog, verified=False)
    seen.patch(draft_id, {"additional_confirmed": True})
    res = seen.verify_and_submit(draft_id)
    assert res.status_code == 201, res.json()
    request_id = res.json()["id"]

    admin = make_user("super_admin", name=ADMIN_NAME)
    body = {} if action == "accept" else {"reason": "under_15_days"}
    decided = client.post(
        f"/api/admin/requests/{request_id}/{action}",
        json=body,
        headers=auth_header(login(client, admin.phone)),
    )
    assert decided.status_code == 200, decided.json()

    mine = seen.get(f"/api/requests/{request_id}").json()
    seen.get("/api/requests")
    # The decision fields are there, and nothing more (FR-011).
    assert {"rejection_reason", "rejection_label", "rejected_at"} <= set(mine)
    assert not {"warnings", "decision", "approval_warnings", "approved_by"} & set(mine)
    seen.assert_hides(old, OTHER_PHONE, OTHER_NID, ADMIN_NAME, '"despite_warnings"', '"record"')


@pytest.mark.parametrize("action", ["accept", "reject"])
def test_notifications_show_nothing_more(client, db, h, catalog, make_user, action):
    """specs/012 FR-019, FR-023: a notification carries the event, the number, the marketer's own
    subscriber's name and a reason label; no phone, numbers, address, note, admin or other
    record."""
    old = _record(db, make_user, family_number=FAMILY, national_id=OTHER_NID, phone=OTHER_PHONE)
    seen = Seen(client, h)
    draft_id = complete_draft(client, h, catalog, verified=False)
    seen.patch(draft_id, {"additional_confirmed": True})
    res = seen.verify_and_submit(draft_id)
    assert res.status_code == 201, res.json()
    mine = res.json()

    admin = make_user("super_admin", name=ADMIN_NAME)
    body = {} if action == "accept" else {"reason": "other", "note": "نص ملاحظة المراجع"}
    decided = client.post(
        f"/api/admin/requests/{mine['id']}/{action}",
        json=body,
        headers=auth_header(login(client, admin.phone)),
    )
    assert decided.status_code == 200, decided.json()

    listed = client.get("/api/notifications", headers=h)
    assert listed.status_code == 200, listed.json()
    (item,) = listed.json()["items"]
    assert set(item) == {
        "id",
        "kind",
        "request_id",
        "number_label",
        "full_name",
        "deleted",
        "reason_label",
        "created_at",
        "read_at",
    }
    for secret in (mine["phone"], NID, FAMILY, mine["address"], "نص ملاحظة المراجع", ADMIN_NAME):
        assert secret not in listed.text
    seen.bodies.append(listed.text)
    seen.assert_hides(old, OTHER_PHONE, OTHER_NID, ADMIN_NAME)


def test_a_pin_shows_nothing_new_to_the_marketer(client, db, make_user):
    """specs/010 T049 (FR-011): after a pin that turns the request into «اشتراك إضافي» and adds a
    linked record, the marketer sees the new type and nothing of the pin, the warnings or the
    record."""
    from tests.helpers.review import pending_request

    old = _record(db, make_user, family_number=OTHER_FAMILY, national_id=OTHER_NID)
    owner = make_user("marketer")
    seen = Seen(client, marketer_headers(client, owner))
    request = pending_request(
        db,
        owner,
        [("numbers_edited", None, {"fields": ["family_number"]})],
        card_fields={"family_number": {"original": OTHER_FAMILY, "edited": True}},
    )
    admin = make_user("super_admin", name=ADMIN_NAME)
    res = client.post(
        f"/api/admin/requests/{request.id}/pin",
        json={"field": "family_number", "source": "reading"},
        headers=auth_header(login(client, admin.phone)),
    )
    assert res.status_code == 200, res.json()
    assert res.json()["type"] == "additional"

    mine = seen.get(f"/api/requests/{request.id}").json()
    seen.get("/api/requests")
    assert mine["type"] == "additional"
    # The reason codes are part of the marketer's view since 008; their details are not.
    assert not {"pins", "numbers", "warnings", "decision"} & set(mine)
    seen.assert_hides(
        old, OTHER_NID, ADMIN_NAME, '"pins"', '"previous_value"', '"warnings"', '"record"'
    )


def test_deleted_request_shows_no_admin_or_erased_data(client, db, make_user):
    """specs/011 T054: a deleted request tells the marketer the reason only: no admin name and no
    erased value."""
    from tests.helpers.requests import mark_deleted
    from tests.helpers.review import admin_with

    me = make_user("marketer")
    own = marketer_headers(client, me)
    request = request_factory(
        db, me, status="pending_review", full_name=SECRET_NAME, username=SECRET_USERNAME
    )
    secrets = [SECRET_NAME, SECRET_USERNAME, request.phone, request.address, request.national_id]
    mark_deleted(db, request, admin_with(make_user, "review", "delete", name="أدمن الحذف السري"))

    blob = client.get(f"/api/requests/{request.id}", headers=own).text
    blob += client.get("/api/requests", headers=own).text
    for secret in [*secrets, "أدمن الحذف السري"]:
        assert secret not in blob, secret


def test_links_of_another_marketer_never_reach_this_one(client, db, make_user) -> None:
    """specs/013 FR-019, T034: the home counter, its latest links and the «تم الربط» tab hold the
    caller's links only, and never who linked."""
    me, other = make_user("marketer"), make_user("marketer")
    mine = request_factory(db, me, status="linked")
    theirs = request_factory(db, other, status="linked", full_name=SECRET_NAME)
    h = auth_header(login(client, me.phone))

    dashboard = client.get("/api/marketer/dashboard", headers=h)
    tab = client.get("/api/requests", params={"status": "linked"}, headers=h)
    page = client.get(f"/api/requests/{theirs.id}", headers=h)

    assert dashboard.json()["linked_this_month"] == 1
    assert [r["id"] for r in dashboard.json()["recent_links"]] == [mine.id]
    assert [r["id"] for r in tab.json()["items"]] == [mine.id]
    assert page.status_code == 404
    for res in (dashboard, tab):
        assert SECRET_NAME not in res.text
        assert theirs.number_label not in res.text
        assert "linked_by" not in res.text
