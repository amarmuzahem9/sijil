"""US4 — «حسابي»: only the main admin renames themselves; nobody edits their phone (§3.5)."""

import pytest
from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import auth_header, login


def test_main_admin_renames_self(client, db, make_user) -> None:
    main = make_user("super_admin")
    h = auth_header(login(client, main.phone))
    r = client.patch("/api/auth/me", json={"name": "  المدير   العام "}, headers=h)
    assert r.status_code == 200 and r.json()["name"] == "المدير العام"
    assert client.get("/api/auth/me", headers=h).json()["name"] == "المدير العام"
    entry = db.execute(select(AuditLog).where(AuditLog.action == "user.updated")).scalar_one()
    assert entry.actor_id == main.id and entry.entity_id == str(main.id)
    assert entry.after == {"name": "المدير العام"}


@pytest.mark.parametrize("role", ["admin", "marketer"])
def test_others_cannot_rename(client, make_user, role) -> None:
    u = make_user(role)
    r = client.patch(
        "/api/auth/me", json={"name": "اسم جديد"}, headers=auth_header(login(client, u.phone))
    )
    assert (r.status_code, r.json()["code"]) == (403, "forbidden")


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"name": "مدير", "phone": "07700000999"}, "validation_error"),
        ({"phone": "07700000999"}, "validation_error"),
        ({"name": "ا"}, "invalid_name"),
        ({"name": "ا" * 101}, "invalid_name"),
    ],
)
def test_rename_validation(client, make_user, body, code) -> None:
    main = make_user("super_admin")
    r = client.patch("/api/auth/me", json=body, headers=auth_header(login(client, main.phone)))
    assert (r.status_code, r.json()["code"]) == (422, code)
