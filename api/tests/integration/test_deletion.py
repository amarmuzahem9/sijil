"""«حذف مشترك»: erase a pending or rejected request in place (specs/011 US1: FR-002 to FR-012,
FR-017, FR-018; research R1 to R5, R12). Synthetic data only."""

import logging
import uuid

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import AuditLog, Request, RequestImage, RequestNumberPin
from app.models.draft import Draft
from app.models.otp import OtpChallenge
from app.models.request import ERASED_COLUMNS
from app.services import image_store
from tests.helpers.requests import add_images, add_otp_rows, add_pin, request_factory
from tests.helpers.review import admin_with, headers_for

KEPT = (
    "number",
    "marketer_id",
    "type",
    "status",
    "area_id",
    "tower_id",
    "plan_id",
    "area_name",
    "tower_code",
    "tower_name",
    "plan_name",
    "trial_price",
    "second_price",
    "otp_verified_at",
    "submitted_at",
    "rejected_at",
    "rejected_by",
    "rejection_reason",
)


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.fixture
def deleter(make_user):
    return admin_with(make_user, "review", "delete", name="أدمن الحذف")


def _delete(client, h, request_id, reason="duplicate", confirm=None, request=None):
    body = {"reason": reason, "confirm_number": confirm}
    if confirm is None and request is not None:
        body["confirm_number"] = request.number_label
    return client.post(f"/api/admin/requests/{request_id}/delete", json=body, headers=h)


def _arabic_indic(n: int) -> str:
    return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


def _snapshot(request: Request) -> dict:
    return {c: getattr(request, c) for c in KEPT}


# --- erasure (T015) ------------------------------------------------------------------------------


def test_pending_request_is_erased_in_place(client, db, uploads, marketer, deleter) -> None:
    request = request_factory(db, marketer, status="pending_review", national_id_check={"x": 1})
    images = add_images(db, request, uploads)
    add_pin(db, request, deleter)
    orphan = add_otp_rows(db, request.phone, 2)
    draft = Draft(id=uuid.uuid4(), marketer_id=marketer.id, phone_input=request.phone)
    db.add(draft)
    db.flush()
    live = add_otp_rows(db, request.phone, 1, draft_id=draft.id)
    kept = _snapshot(request)
    files = [uploads / i.file_name for i in images]
    assert all(f.is_file() for f in files)

    res = _delete(
        client, headers_for(client, deleter), request.id, confirm=_arabic_indic(request.number)
    )

    assert res.status_code == 200, res.text
    db.expire_all()
    row = db.get(Request, request.id)
    for column in ERASED_COLUMNS:
        assert getattr(row, column) is None, column
    assert _snapshot(row) == kept
    assert row.status == "pending_review"
    assert row.deleted_by == deleter.id and row.deletion_reason == "duplicate"
    assert row.deleted_at is not None
    assert db.scalar(select(func.count()).select_from(RequestImage)) == 0
    assert (
        db.scalar(
            select(func.count())
            .select_from(RequestNumberPin)
            .where(RequestNumberPin.request_id == request.id)
        )
        == 0
    )
    assert not any(f.exists() for f in files)
    remaining = set(db.scalars(select(OtpChallenge.id)))
    assert not {o.id for o in orphan} & remaining
    assert {o.id for o in live} <= remaining

    body = res.json()
    assert body["deleted"]["reason"] == "duplicate"
    assert body["deleted"]["by_name"] == "أدمن الحذف"
    assert body["can_delete"] is False
    for field in ("full_name", "national_id", "family_number", "phone", "username", "address"):
        assert body[field] is None, field
    assert body["images"] == [] and body["warnings"] == [] and body["location"] is None


def test_rejected_request_keeps_the_reason_name_and_loses_the_note(
    client, db, uploads, marketer, deleter
) -> None:
    request = request_factory(
        db,
        marketer,
        status="rejected",
        rejection_reason="other",
        rejection_note="ملاحظة المراجع",
        rejected_by=deleter.id,
    )
    kept = _snapshot(request)

    res = _delete(client, headers_for(client, deleter), request.id, "other", request=request)

    assert res.status_code == 200, res.text
    db.expire_all()
    row = db.get(Request, request.id)
    assert row.rejection_note is None and row.full_name is None
    assert _snapshot(row) == kept
    assert row.status == "rejected" and row.deletion_reason == "other"
    decision = res.json()["decision"]
    assert decision["reason"] == "other" and decision["label"] == "سبب آخر"


@pytest.mark.parametrize("typed", ["T3C-{n}", "t3c-{n}", "#T3C-{n}", "{n}", " {n} "])
def test_typed_number_formats(client, db, uploads, marketer, deleter, typed) -> None:
    request = request_factory(db, marketer, status="pending_review")
    confirm = typed.format(n=request.number)
    res = _delete(client, headers_for(client, deleter), request.id, "test", confirm=confirm)
    assert res.status_code == 200, res.text


def test_main_admin_deletes(client, db, uploads, marketer, make_user) -> None:
    request = request_factory(db, marketer, status="pending_review")
    owner = make_user("super_admin")
    res = _delete(client, headers_for(client, owner), request.id, "test", request=request)
    assert res.status_code == 200, res.text


# --- refusals (T016) -----------------------------------------------------------------------------


def _unchanged(db, request: Request, before: dict) -> None:
    db.expire_all()
    row = db.get(Request, request.id)
    assert _snapshot(row) == before and row.deleted_at is None and row.phone is not None


@pytest.mark.parametrize(
    "perms,status,code",
    [
        ((), 404, "request_not_found"),
        (("delete",), 404, "request_not_found"),
        (("review",), 403, "forbidden"),
        (("review", "link", "settings"), 403, "forbidden"),
    ],
)
def test_permission_refusals(client, db, marketer, make_user, perms, status, code) -> None:
    request = request_factory(db, marketer, status="pending_review")
    before = _snapshot(request)
    admin = admin_with(make_user, *perms)
    res = _delete(client, headers_for(client, admin), request.id, request=request)
    assert (res.status_code, res.json()["code"]) == (status, code)
    _unchanged(db, request, before)


def test_marketer_is_refused(client, db, marketer) -> None:
    request = request_factory(db, marketer, status="pending_review")
    res = _delete(client, headers_for(client, marketer), request.id, request=request)
    assert res.status_code in (403, 404)
    assert db.get(Request, request.id).deleted_at is None


def test_missing_request_is_404(client, deleter) -> None:
    res = _delete(client, headers_for(client, deleter), 987654321, confirm="1")
    assert (res.status_code, res.json()["code"]) == (404, "request_not_found")


def test_second_delete_is_409(client, db, uploads, marketer, deleter) -> None:
    request = request_factory(db, marketer, status="pending_review")
    h = headers_for(client, deleter)
    assert _delete(client, h, request.id, request=request).status_code == 200
    res = _delete(client, h, request.id, request=request)
    assert (res.status_code, res.json()["code"]) == (409, "request_deleted")
    assert res.json()["message"] == "تم حذف هذا الطلب مسبقاً"


@pytest.mark.parametrize("status", ["approved", "linked"])
def test_accepted_or_linked_is_refused(client, db, marketer, deleter, status) -> None:
    request = request_factory(db, marketer, status=status)
    before = _snapshot(request)
    res = _delete(client, headers_for(client, deleter), request.id, request=request)
    assert (res.status_code, res.json()["code"]) == (409, "request_not_deletable")
    assert res.json()["message"] == "لا يمكن حذف طلب مقبول أو مربوط"
    _unchanged(db, request, before)


@pytest.mark.parametrize("reason", ["guess", "", "card_unclear"])
def test_unknown_reason_is_422(client, db, marketer, deleter, reason) -> None:
    request = request_factory(db, marketer, status="pending_review")
    before = _snapshot(request)
    res = _delete(client, headers_for(client, deleter), request.id, reason, request=request)
    assert res.status_code == 422
    _unchanged(db, request, before)


@pytest.mark.parametrize("confirm", ["{other}", "", "T3C-", "abc", "{n}x"])
def test_wrong_number_is_422(client, db, marketer, deleter, confirm) -> None:
    request = request_factory(db, marketer, status="pending_review")
    before = _snapshot(request)
    typed = confirm.format(n=request.number, other=request.number + 1)
    res = _delete(client, headers_for(client, deleter), request.id, confirm=typed)
    assert (res.status_code, res.json()["code"]) == (422, "number_mismatch")
    assert res.json()["message"] == "رقم الطلب غير مطابق"
    _unchanged(db, request, before)


def test_extra_fields_are_refused(client, db, marketer, deleter) -> None:
    request = request_factory(db, marketer, status="pending_review")
    res = client.post(
        f"/api/admin/requests/{request.id}/delete",
        json={"reason": "test", "confirm_number": request.number_label, "note": "نص"},
        headers=headers_for(client, deleter),
    )
    assert res.status_code == 422


# --- files (T017) --------------------------------------------------------------------------------


def test_missing_file_still_deletes_and_logs_the_id_only(
    client, db, uploads, marketer, deleter, caplog
) -> None:
    caplog.set_level(logging.INFO)
    request = request_factory(db, marketer, status="pending_review")
    images = add_images(db, request, uploads)
    (uploads / images[0].file_name).unlink()
    phone = request.phone

    res = _delete(client, headers_for(client, deleter), request.id, request=request)

    assert res.status_code == 200, res.text
    assert not (uploads / images[1].file_name).exists()
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert str(images[0].id) in logs
    assert images[0].file_name not in logs and phone not in logs


def test_crash_before_unlink_leaves_only_orphans(
    client, db, uploads, marketer, deleter, monkeypatch
) -> None:
    """The rows are gone with the erasure; files left by a crash are orphans for prune-uploads."""
    from app.services import draft_service

    request = request_factory(db, marketer, status="pending_review")
    images = add_images(db, request, uploads)
    monkeypatch.setattr(image_store, "unlink_quietly", lambda name: None)

    assert (
        _delete(client, headers_for(client, deleter), request.id, request=request).status_code
        == 200
    )

    assert all((uploads / i.file_name).exists() for i in images)
    referenced = draft_service.referenced_file_names(db)
    assert not {i.file_name for i in images} & referenced


# --- audit (T020, here for the deletion entry itself) --------------------------------------------


def test_one_audit_entry_without_personal_data(client, db, uploads, marketer, deleter) -> None:
    request = request_factory(db, marketer, status="pending_review", full_name="اسم سري للحذف")
    add_images(db, request, uploads)
    add_pin(db, request, deleter)

    assert (
        _delete(
            client, headers_for(client, deleter), request.id, "test", request=request
        ).status_code
        == 200
    )

    entries = db.scalars(select(AuditLog).where(AuditLog.action == "request.deleted")).all()
    assert len(entries) == 1
    entry = entries[0]
    assert (entry.actor_id, entry.entity_type, entry.entity_id) == (
        deleter.id,
        "request",
        str(request.number),
    )
    assert entry.before == {"status": "pending_review", "image_count": 2, "pin_count": 1}
    assert entry.after == {"deleted": True, "reason": "test"}
