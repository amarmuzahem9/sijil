"""account_service rules (specs/002 data-model.md, research R3–R6)."""

import json

import pytest
from sqlalchemy import select

from app.errors import AppError
from app.models import AuditLog, UserSession
from app.services import account_service as svc
from tests.conftest import login

TEMP = "Temp-Pass-123"


def _audit(db, user_id, action=None):
    q = select(AuditLog).where(AuditLog.entity_id == str(user_id))
    if action:
        q = q.where(AuditLog.action == action)
    return list(db.execute(q.order_by(AuditLog.id)).scalars())


def _code(fn):
    with pytest.raises(AppError) as exc:
        fn()
    return exc.value.code


@pytest.fixture
def boss(make_user):
    return make_user("super_admin")


def test_create_sets_flag_normalizes_phone_and_audits(db, boss) -> None:
    u = svc.create_account(
        db,
        boss,
        role="marketer",
        name="  مسوّق   تجريبي ",
        phone="+964 770 000 1301",
        temporary_password=TEMP,
    )
    assert (u.name, u.phone, u.must_change_password, u.is_active) == (
        "مسوّق تجريبي",
        "07700001301",
        True,
        True,
    )
    [entry] = _audit(db, u.id)
    assert entry.action == "user.created" and entry.actor_id == boss.id
    assert entry.after["role"] == "marketer" and entry.before is None


def test_phone_unique_across_roles_and_states(db, boss, make_user) -> None:
    make_user("admin", phone="07700001302", is_active=False)
    assert (
        _code(
            lambda: svc.create_account(
                db,
                boss,
                role="marketer",
                name="مسوّق",
                phone="٠٧٧٠٠٠٠١٣٠٢",
                temporary_password=TEMP,
            )
        )
        == "phone_taken"
    )


@pytest.mark.parametrize(
    ("name", "phone", "pw", "code"),
    [
        ("ا", "07700001303", TEMP, "invalid_name"),
        ("   ", "07700001303", TEMP, "invalid_name"),
        ("ا" * 101, "07700001303", TEMP, "invalid_name"),
        ("اسم صالح", "12345", TEMP, "invalid_phone"),
        ("اسم صالح", "07700001303", "short7!", "weak_password"),
    ],
)
def test_create_validation_codes(db, boss, name, phone, pw, code) -> None:
    assert (
        _code(
            lambda: svc.create_account(
                db, boss, role="marketer", name=name, phone=phone, temporary_password=pw
            )
        )
        == code
    )


def test_permissions_only_for_admins_and_normalized(db, boss) -> None:
    a = svc.create_account(
        db,
        boss,
        role="admin",
        name="أدمن تجريبي",
        phone="07700001304",
        temporary_password=TEMP,
        permissions=["reports", "marketers", "reports"],
    )
    assert a.permissions == ["marketers", "reports"]
    m = svc.create_account(
        db,
        boss,
        role="marketer",
        name="مسوّق",
        phone="07700001305",
        temporary_password=TEMP,
        permissions=["review"],
    )
    assert m.permissions == []
    assert (
        _code(
            lambda: svc.create_account(
                db,
                boss,
                role="admin",
                name="أدمن",
                phone="07700001306",
                temporary_password=TEMP,
                permissions=["nope"],
            )
        )
        == "validation_error"
    )


def test_update_noop_writes_nothing_and_change_kinds_audited_separately(
    db, boss, make_user
) -> None:
    a = make_user("admin")
    old_name = a.name
    svc.update_account(db, boss, a, name=a.name, phone=a.phone, permissions=[])
    assert _audit(db, a.id) == []
    svc.update_account(db, boss, a, name="اسم جديد", permissions=["settings"])
    actions = [e.action for e in _audit(db, a.id)]
    assert actions == ["user.updated", "user.permissions_changed"]
    upd, perm = _audit(db, a.id)
    assert upd.before == {"name": old_name} and upd.after == {"name": "اسم جديد"}
    assert perm.before == {"permissions": []} and perm.after == {"permissions": ["settings"]}


def test_update_phone_to_taken_refused_same_phone_allowed(db, boss, make_user) -> None:
    m1, m2 = make_user("marketer"), make_user("marketer")
    assert _code(lambda: svc.update_account(db, boss, m1, phone=m2.phone)) == "phone_taken"
    svc.update_account(db, boss, m1, phone=m1.phone)  # unchanged → fine, no-op


def test_deactivate_revokes_sessions_and_reactivate_keeps_them_revoked(
    db, client, boss, make_user
) -> None:
    m = make_user("marketer")
    login(client, m.phone)
    login(client, m.phone)
    svc.set_active(db, boss, m, False)
    sessions = list(db.execute(select(UserSession).where(UserSession.user_id == m.id)).scalars())
    assert len(sessions) == 2
    assert all(s.revoked_at is not None and s.revoke_reason == "deactivated" for s in sessions)
    svc.set_active(db, boss, m, False)  # no-op
    svc.set_active(db, boss, m, True)
    assert all(s.revoked_at is not None for s in sessions)
    assert [e.action for e in _audit(db, m.id)] == ["user.deactivated", "user.reactivated"]


def test_reset_password_sets_flag_and_revokes(db, client, boss, make_user) -> None:
    m = make_user("marketer")
    login(client, m.phone)
    old_hash = m.password_hash
    svc.reset_password(db, boss, m, TEMP)
    assert m.password_hash != old_hash and m.must_change_password is True
    s = db.execute(select(UserSession).where(UserSession.user_id == m.id)).scalar_one()
    assert s.revoke_reason == "password_reset"
    assert _code(lambda: svc.reset_password(db, boss, m, "short")) == "weak_password"


def test_main_admin_is_protected(db, boss, make_user) -> None:
    other = make_user("super_admin")
    assert _code(lambda: svc.set_active(db, boss, other, False)) == "protected_account"
    assert _code(lambda: svc.reset_password(db, boss, other, TEMP)) == "protected_account"
    assert _code(lambda: svc.update_account(db, boss, other, permissions=["review"])) == (
        "protected_account"
    )
    assert other.is_active is True


def test_get_target_is_role_scoped(db, boss, make_user) -> None:
    a = make_user("admin")
    assert svc.get_target(db, a.id, "admin") is a
    assert _code(lambda: svc.get_target(db, a.id, "marketer")) == "not_found"
    assert _code(lambda: svc.get_target(db, boss.id, "admin")) == "not_found"
    assert _code(lambda: svc.get_target(db, 999_999_999, "admin")) == "not_found"


def test_audit_never_contains_secrets(db, boss, make_user) -> None:
    m = svc.create_account(
        db, boss, role="marketer", name="مسوّق", phone="07700001307", temporary_password=TEMP
    )
    svc.reset_password(db, boss, m, "Other-Temp-456")
    blob = json.dumps([[e.before, e.after] for e in _audit(db, m.id)], ensure_ascii=False)
    for needle in (TEMP, "Other-Temp-456", "password_hash", "token", "$argon2"):
        assert needle not in blob
