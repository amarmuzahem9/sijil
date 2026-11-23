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
