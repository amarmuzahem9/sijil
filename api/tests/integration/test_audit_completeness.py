"""SC-005: every account action writes exactly one entry per kind of change, never a secret."""

import json

from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import TEST_PASSWORD, auth_header, login

TEMP_ADMIN, TEMP_MARKETER, RESET = "Temp-Admin-111", "Temp-Mark-222", "Reset-Pass-333"
NEW_OWN = "Own-New-Pass-444"


def test_every_action_once_and_no_secrets(client, db, make_user) -> None:
    main = make_user("super_admin")
    h = auth_header(login(client, main.phone))

    admin = client.post(
        "/api/admin/admins",
        headers=h,
        json={
            "name": "أدمن الاكتمال",
            "phone": "07700000151",
            "temporary_password": TEMP_ADMIN,
            "permissions": ["marketers"],
        },
    ).json()
    marketer = client.post(
        "/api/admin/marketers",
        headers=h,
        json={"name": "مسوّق الاكتمال", "phone": "07700000251", "temporary_password": TEMP_MARKETER},
    ).json()
    a, m, me = str(admin["id"]), str(marketer["id"]), str(main.id)

    client.patch(
        f"/api/admin/admins/{a}",
        headers=h,
        json={"name": "أدمن معدّل", "permissions": ["marketers", "review"]},
    )
    client.patch(f"/api/admin/marketers/{m}", headers=h, json={"phone": "07700000252"})
    client.post(f"/api/admin/marketers/{m}/deactivate", headers=h)
    client.post(f"/api/admin/marketers/{m}/reactivate", headers=h)
    client.post(
        f"/api/admin/admins/{a}/reset-password", headers=h, json={"temporary_password": RESET}
    )
    client.patch("/api/auth/me", headers=h, json={"name": "المدير الجديد"})
    r = client.post(
        "/api/auth/change-password",
        headers=h,
        json={"current_password": TEST_PASSWORD, "new_password": NEW_OWN},
    )
    assert r.status_code == 200

    entries = list(db.execute(select(AuditLog).order_by(AuditLog.id)).scalars())
    assert [(e.action, e.entity_id) for e in entries] == [
        ("user.created", a),
        ("user.created", m),
        ("user.updated", a),
        ("user.permissions_changed", a),
        ("user.updated", m),
        ("user.deactivated", m),
        ("user.reactivated", m),
        ("user.password_reset", a),
        ("user.updated", me),
        ("user.password_changed", me),
    ]
    assert all(e.actor_id == main.id for e in entries)

    blob = json.dumps([[e.before, e.after] for e in entries], ensure_ascii=False)
    for secret in (TEMP_ADMIN, TEMP_MARKETER, RESET, NEW_OWN, TEST_PASSWORD, "$argon2"):
        assert secret not in blob
    for key in ("password_hash", "token", "temporary_password"):
        assert f'"{key}"' not in blob


def test_submission_actions_are_audited_once_without_card_data(
    client, db, make_user, tmp_path, monkeypatch
) -> None:
    """Feature 008 (T046): one `request.submitted` per request, one `request.submit_refused` per
    refused attempt, by the marketer, with no card data."""
    from app.config import get_settings
    from app.services.card_reader_fake_data import FAMILY, NID
    from tests.helpers.requests import request_factory
    from tests.helpers.submit import complete_draft, make_catalog, marketer_headers, submit

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    catalog = make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))
    marketer = make_user("marketer")
    h = marketer_headers(client, marketer)

    ok = submit(client, h, complete_draft(client, h, catalog)).json()
    refused_id = complete_draft(client, h, catalog, phone="07801234599", read_card=False)
    request_factory(db, make_user("marketer"), phone="07801234599")
    db.commit()
    assert submit(client, h, refused_id).json()["code"] == "phone_used"

    entries = list(
        db.scalars(select(AuditLog).where(AuditLog.action.like("request.%")).order_by(AuditLog.id))
    )
    assert [(e.action, e.entity_type, e.entity_id) for e in entries] == [
        ("request.submitted", "request", str(ok["number"])),
        ("request.submit_refused", "draft", refused_id),
    ]
    assert all(e.actor_id == marketer.id for e in entries)
    blob = json.dumps([[e.before, e.after] for e in entries], ensure_ascii=False)
    for secret in (NID, FAMILY, "07801234567", "07801234599", ok["full_name"]):
        assert secret not in blob


def test_existing_subscriber_actions_are_audited_once_without_card_data(
    client, db, make_user, tmp_path, monkeypatch
) -> None:
    """Feature 009 (T045, FR-014): choosing and withdrawing a return, opening «الاتصال بالإدارة»
    and submitting a return each write one entry by the marketer, with the draft id and the basis
    only: no card number, no phone, no name, no matched record."""
    from app.config import get_settings
    from app.services.card_reader_fake_data import FAMILY, NID
    from tests.helpers.requests import request_factory
    from tests.helpers.submit import (
        complete_draft,
        make_catalog,
        marketer_headers,
        patch,
        submit,
        verify,
    )

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    catalog = make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))
    marketer = make_user("marketer")
    h = marketer_headers(client, marketer)
    old = request_factory(
        db,
        make_user("marketer"),
        national_id=NID,
        national_id_input=NID,
        family_number=FAMILY,
        phone="07709990003",
        full_name="اسم سابق سري",
    )

    draft_id = complete_draft(client, h, catalog, verified=False)
    patch(client, h, draft_id, {"return_chosen": True})
    patch(client, h, draft_id, {"return_chosen": False})
    patch(client, h, draft_id, {"return_chosen": True})
    assert client.post(f"/api/drafts/{draft_id}/contact-admin", headers=h).status_code == 204
    verify(client, h, draft_id)
    ok = submit(client, h, draft_id).json()

    entries = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.action.like("draft.%") | AuditLog.action.like("request.%"))
            .where(AuditLog.actor_id == marketer.id)
            .order_by(AuditLog.id)
        )
    )
    assert [(e.action, e.entity_id) for e in entries] == [
        ("draft.return_chosen", draft_id),
        ("draft.return_withdrawn", draft_id),
        ("draft.return_chosen", draft_id),
        ("draft.contact_admin_opened", draft_id),
        ("request.submitted", str(ok["number"])),
    ]
    assert entries[0].after == {"basis": "identity"}
    assert entries[-1].after["reasons"] == ["return"]
    blob = json.dumps([[e.before, e.after] for e in entries], ensure_ascii=False)
    for secret in (NID, FAMILY, "07801234567", "07709990003", old.full_name, old.username):
        assert secret not in blob
    assert f'"{old.id}"' not in blob and str(old.draft_id) not in blob


def test_review_decisions_are_audited_once_without_card_data(client, db, make_user) -> None:
    """Feature 010 (T038, FR-017): accept and reject each write one entry by the admin, with the
    number, the status before and after, the reason or the commission answer, and no card number,
    phone or name."""
    from tests.helpers.requests import request_factory

    marketer = make_user("marketer")
    admin = make_user("super_admin")
    h = auth_header(login(client, admin.phone))
    one = request_factory(db, marketer, status="pending_review", full_name="اسم سري للقبول")
    two = request_factory(db, marketer, status="pending_review", full_name="اسم سري للرفض")

    assert (
        client.post(f"/api/admin/requests/{one.id}/accept", json={}, headers=h).status_code == 200
    )
    res = client.post(
        f"/api/admin/requests/{two.id}/reject", json={"reason": "card_unclear"}, headers=h
    )
    assert res.status_code == 200

    entries = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.action.in_(("request.approved", "request.rejected")))
            .order_by(AuditLog.id)
        )
    )
    assert [(e.action, e.entity_id, e.actor_id) for e in entries] == [
        ("request.approved", str(one.number), admin.id),
        ("request.rejected", str(two.number), admin.id),
    ]
    blob = json.dumps([[e.before, e.after] for e in entries], ensure_ascii=False)
    for request in (one, two):
        for secret in (
            request.national_id,
            request.family_number,
            request.phone,
            request.full_name,
        ):
            assert secret not in blob, secret


def test_a_pin_is_audited_by_its_pin_row(client, db, make_user) -> None:
    """Feature 010 (T048, constitution III v1.2.1): one entry per pin, holding `pin_id`; the values
    before and after are in that pin row, never in the entry."""
    from app.models import RequestNumberPin
    from tests.helpers.review import pending_request

    marketer = make_user("marketer")
    admin = make_user("super_admin")
    h = auth_header(login(client, admin.phone))
    request = pending_request(
        db,
        marketer,
        [("numbers_edited", None, {"fields": ["national_id"]})],
        full_name="اسم سري للتثبيت",
        card_fields={"national_id": {"original": "199055556666", "edited": True}},
    )
    old_value = request.national_id

    res = client.post(
        f"/api/admin/requests/{request.id}/pin",
        json={"field": "national_id", "source": "reading"},
        headers=h,
    )
    assert res.status_code == 200, res.json()

    (entry,) = db.scalars(select(AuditLog).where(AuditLog.action == "request.numbers_pinned"))
    assert (entry.entity_type, entry.entity_id, entry.actor_id) == (
        "request",
        str(request.number),
        admin.id,
    )
    assert entry.before == {"type": "new", "field_changed": True}
    assert entry.after == {
        "pin_id": entry.after["pin_id"],
        "field": "national_id",
        "source": "reading",
        "type": "new",
        "reasons_added": [],
        "reasons_not_applicable": [],
        "numbers_edited_resolved": True,
    }
    row = db.get(RequestNumberPin, entry.after["pin_id"])
    assert (row.request_id, row.previous_value, row.value) == (
        request.id,
        old_value,
        "199055556666",
    )
    blob = json.dumps([entry.before, entry.after], ensure_ascii=False)
    for secret in (
        old_value,
        "199055556666",
        request.family_number,
        request.phone,
        request.full_name,
    ):
        assert secret not in blob, secret


def test_a_deletion_is_audited_once_without_personal_data(
    client, db, make_user, tmp_path, monkeypatch
) -> None:
    """Feature 011 (T020, FR-018): one `request.deleted` entry by the admin, with the number,
    the status before, the counts and the reason, and no personal value."""
    from app.config import get_settings
    from tests.helpers.requests import add_images, add_pin, request_factory

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    marketer = make_user("marketer")
    admin = make_user("super_admin")
    request = request_factory(db, marketer, status="pending_review", full_name="اسم سري للحذف")
    add_images(db, request, tmp_path)
    add_pin(db, request, admin)
    secrets = [
        request.national_id,
        request.family_number,
        request.phone,
        request.full_name,
        request.username,
        request.address,
        request.landmark,
        "199000000099",  # the pin's value
    ]
    h = auth_header(login(client, admin.phone))
    res = client.post(
        f"/api/admin/requests/{request.id}/delete",
        json={"reason": "duplicate", "confirm_number": request.number_label},
        headers=h,
    )
    assert res.status_code == 200, res.text

    entries = list(db.scalars(select(AuditLog).where(AuditLog.action == "request.deleted")))
    assert [(e.entity_type, e.entity_id, e.actor_id) for e in entries] == [
        ("request", str(request.number), admin.id)
    ]
    assert entries[0].before == {"status": "pending_review", "image_count": 2, "pin_count": 1}
    assert entries[0].after == {"deleted": True, "reason": "duplicate"}
    blob = json.dumps([entries[0].before, entries[0].after], ensure_ascii=False)
    for secret in secrets:
        assert secret not in blob, secret
