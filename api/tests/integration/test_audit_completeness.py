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
