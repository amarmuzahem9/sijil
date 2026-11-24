"""The marketer's own requests (specs/008 T020, FR-019, contracts GET /api/requests)."""

from pathlib import Path

import pytest

from app.config import get_settings
from app.services.card_reader_fake_data import FAMILY, NID
from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.requests import request_factory
from tests.helpers.submit import complete_draft, make_catalog, marketer_headers, submit


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    get_otp_sender().outbox.clear()
    return tmp_path


@pytest.fixture
def catalog(client, make_user):
    return make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))


@pytest.fixture
def me(make_user):
    return make_user("marketer")


@pytest.fixture
def h(client, me):
    return marketer_headers(client, me)


def test_list_is_own_newest_first_and_filters(client, db, h, make_user, catalog) -> None:
    approved = submit(client, h, complete_draft(client, h, catalog)).json()
    pending = submit(
        client, h, complete_draft(client, h, catalog, phone="07801234568", read_card=False)
    ).json()
    request_factory(db, make_user("marketer"))  # someone else's

    items = client.get("/api/requests", headers=h).json()["items"]
    assert [i["id"] for i in items] == [pending["id"], approved["id"]]
    assert set(items[0]) == {
        "id",
        "number_label",
        "full_name",
        "status",
        "type",
        "submitted_at",
        "tower_code",
        "tower_name",
        "rejection_label",
        # specs/011 R11
        "deleted_at",
        "deletion_label",
        # specs/013 R8
        "linked_at",
    }
    assert items[1]["number_label"] == approved["number_label"]

    only = client.get("/api/requests", params={"status": "pending_review"}, headers=h)
    assert [i["id"] for i in only.json()["items"]] == [pending["id"]]
    both = client.get(
        "/api/requests", params=[("status", "approved"), ("status", "pending_review")], headers=h
    )
    assert len(both.json()["items"]) == 2


def test_get_own_request_and_hide_the_rest(client, db, h, make_user, catalog) -> None:
    created = submit(client, h, complete_draft(client, h, catalog)).json()
    res = client.get(f"/api/requests/{created['id']}", headers=h)
    assert res.status_code == 200 and res.json() == created
    for secret in (NID, FAMILY, "card_readings", "raw"):
        assert secret not in res.text

    other = request_factory(db, make_user("marketer"))
    res = client.get(f"/api/requests/{other.id}", headers=h)
    assert (res.status_code, res.json()["code"]) == (404, "request_not_found")
    assert client.get("/api/requests/999999", headers=h).status_code == 404


def test_username_hidden_until_approved(client, db, h, me) -> None:
    pending = request_factory(db, me, status="pending_review")
    body = client.get(f"/api/requests/{pending.id}", headers=h).json()
    assert body["username"] is None and body["result"] == "pending_review"


def test_admins_cannot_use_the_marketer_routes(client, make_user) -> None:
    admin = auth_header(login(client, make_user("super_admin").phone))
    assert client.get("/api/requests", headers=admin).status_code == 403


def test_request_carries_the_copy_details_fields(client, db, h, me, catalog) -> None:
    """«نسخ التفاصيل» (system.md v1.11 §5.5): address, landmark and the marketer's name."""
    created = submit(client, h, complete_draft(client, h, catalog)).json()
    assert (created["address"], created["landmark"]) == ("حي تجريبي", "قرب نقطة تجريبية")
    assert created["marketer_name"] == me.name
    body = client.get(f"/api/requests/{created['id']}", headers=h).json()
    assert body["marketer_name"] == me.name


def test_tower_name_is_fixed_at_submission(client, db, h, catalog, make_user) -> None:
    """system.md v1.12 §5: the tower name is copied with the request; renaming the tower later
    does not change it."""
    created = submit(client, h, complete_draft(client, h, catalog)).json()
    assert created["tower_name"] == "برج 3"
    admin = auth_header(login(client, make_user("super_admin").phone))
    res = client.patch(
        f"/api/admin/settings/towers/{catalog['alm03']['id']}",
        json={"name": "برج جديد"},
        headers=admin,
    )
    assert res.status_code == 200, res.json()
    body = client.get(f"/api/requests/{created['id']}", headers=h).json()
    assert body["tower_name"] == "برج 3"


# --- after the admin's decision (specs/010 T027, FR-011, research R11) ---------------------------


def _decide(client, make_user, request_id, action, body=None):
    admin = make_user("super_admin")
    res = client.post(
        f"/api/admin/requests/{request_id}/{action}",
        json=body or {},
        headers=auth_header(login(client, admin.phone)),
    )
    assert res.status_code == 200, res.json()


def _pending(db, me):
    return request_factory(db, me, status="pending_review", type="new")


def test_accepted_request_shows_approval_and_username(client, db, h, me, make_user) -> None:
    request = _pending(db, me)
    _decide(client, make_user, request.id, "accept")

    body = client.get(f"/api/requests/{request.id}", headers=h).json()
    assert (body["status"], body["result"]) == ("approved", "approved")
    assert body["username"] == request.username
    assert body["approved_at"] is not None
    assert (body["rejection_reason"], body["rejection_label"], body["rejected_at"]) == (
        None,
        None,
        None,
    )


def test_rejected_with_other_shows_the_note(client, db, h, me, make_user) -> None:
    request = _pending(db, me)
    _decide(client, make_user, request.id, "reject", {"reason": "other", "note": "طلب مكرر"})

    body = client.get(f"/api/requests/{request.id}", headers=h).json()
    assert (body["status"], body["result"]) == ("rejected", "rejected")
    assert (body["rejection_reason"], body["rejection_label"]) == ("other", "طلب مكرر")
    assert body["rejected_at"] is not None
    assert body["username"] is None


def test_rejected_with_a_fixed_reason_shows_its_label(client, db, h, me, make_user) -> None:
    request = _pending(db, me)
    _decide(client, make_user, request.id, "reject", {"reason": "card_unclear"})

    body = client.get(f"/api/requests/{request.id}", headers=h).json()
    assert body["rejection_label"] == "صورة البطاقة غير واضحة"


def test_rejected_list_rows_carry_the_reason(client, db, h, me, make_user) -> None:
    request = _pending(db, me)
    _decide(client, make_user, request.id, "reject", {"reason": "numbers_mismatch"})

    items = client.get("/api/requests", params={"status": "rejected"}, headers=h).json()["items"]
    assert [i["id"] for i in items] == [request.id]
    assert items[0]["rejection_label"] == "الأرقام غير مطابقة للبطاقة"


# --- specs/011 T054: the marketer's view of a deleted request -----------------------------------

DELETED_KEPT = {
    "id",
    "number",
    "number_label",
    "type",
    "status",
    "result",
    "tower_code",
    "tower_name",
    "submitted_at",
    "deleted_at",
    "deletion_label",
    "reasons",
}


def _delete_as_admin(client, make_user, request, reason="duplicate"):
    admin = make_user("super_admin")
    res = client.post(
        f"/api/admin/requests/{request.id}/delete",
        json={"reason": reason, "confirm_number": request.number_label},
        headers=auth_header(login(client, admin.phone)),
    )
    assert res.status_code == 200, res.json()


def test_deleted_request_detail_keeps_only_the_kept_fields(client, db, h, me, make_user) -> None:
    request = _pending(db, me)
    tower_code, tower_name = request.tower_code, request.tower_name
    _delete_as_admin(client, make_user, request, "test")

    res = client.get(f"/api/requests/{request.id}", headers=h)

    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["status"], body["result"]) == ("pending_review", "deleted")
    assert (body["tower_code"], body["tower_name"]) == (tower_code, tower_name)
    assert body["deletion_label"] == "طلب تجريبي"
    assert body["deleted_at"] is not None
    assert body["reasons"] == []
    for key, value in body.items():
        if key not in DELETED_KEPT:
            assert value is None, key


def test_deleted_rejected_request_shows_the_reason_name_only(client, db, h, me, make_user) -> None:
    request = _pending(db, me)
    _decide(client, make_user, request.id, "reject", {"reason": "other", "note": "ملاحظة سرية"})
    _delete_as_admin(client, make_user, request, "entry_error")

    body = client.get(f"/api/requests/{request.id}", headers=h).json()
    assert (body["status"], body["result"]) == ("rejected", "deleted")
    assert body["deletion_label"] == "خطأ إدخال"
    assert "ملاحظة سرية" not in str(body)

    items = client.get("/api/requests", params={"status": "rejected"}, headers=h).json()["items"]
    assert items[0]["rejection_label"] == "سبب آخر"


def test_deleted_request_stays_in_the_list_under_its_status(client, db, h, me, make_user) -> None:
    kept = _pending(db, me)
    gone = _pending(db, me)
    tower_name = gone.tower_name
    _delete_as_admin(client, make_user, gone)

    res = client.get("/api/requests", headers=h)
    assert res.status_code == 200, res.text
    items = {i["id"]: i for i in res.json()["items"]}
    assert set(items) == {kept.id, gone.id}
    row = items[gone.id]
    assert row["full_name"] is None
    assert row["status"] == "pending_review"
    assert row["deletion_label"] == "طلب مكرر" and row["deleted_at"] is not None
    assert row["tower_name"] == tower_name
    assert items[kept.id]["deleted_at"] is None and items[kept.id]["full_name"]

    pending = client.get("/api/requests", params={"status": "pending_review"}, headers=h).json()
    assert gone.id in {i["id"] for i in pending["items"]}
