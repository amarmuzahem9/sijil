from sqlalchemy import select

from app.cli import bootstrap
from app.config import get_settings
from app.core.security import verify_password
from app.models import AuditLog, User

BOOT_PASSWORD = "Boot-Passw0rd-xyz"


def _settings(**overrides):
    values = {
        "superadmin_phone": "+964 770 555 0001",
        "superadmin_name": "الأدمن الرئيسي",
        "superadmin_password": BOOT_PASSWORD,
    } | overrides
    return get_settings().model_copy(update=values)


def _super_admins(db):
    return db.scalars(select(User).where(User.role == "super_admin")).all()


def test_creates_main_admin_once(db, capsys) -> None:
    assert bootstrap(db, _settings()) == 0
    admins = _super_admins(db)
    assert len(admins) == 1
    admin = admins[0]
    assert admin.phone == "07705550001"
    assert admin.must_change_password is True and admin.permissions == []
    assert verify_password(admin.password_hash, BOOT_PASSWORD)

    audit = db.scalars(select(AuditLog).where(AuditLog.action == "user.bootstrap_created")).one()
    assert audit.actor_id is None and audit.entity_id == str(admin.id)
    assert audit.after == {"name": "الأدمن الرئيسي", "phone": "07705550001", "role": "super_admin"}

    out = capsys.readouterr()
    assert BOOT_PASSWORD not in out.out + out.err


def test_second_run_changes_nothing(db) -> None:
    assert bootstrap(db, _settings()) == 0
    first = _super_admins(db)[0]
    original_hash = first.password_hash

    other = _settings(superadmin_phone="07705550002", superadmin_password="Another-Passw0rd")
    assert bootstrap(db, other) == 0
    admins = _super_admins(db)
    assert len(admins) == 1 and admins[0].phone == "07705550001"
    assert admins[0].password_hash == original_hash


def test_invalid_config_without_admin_fails(db, capsys) -> None:
    secret = "short"
    assert bootstrap(db, _settings(superadmin_phone="123", superadmin_password=secret)) == 1
    assert _super_admins(db) == []
    err = capsys.readouterr().err
    assert "SUPERADMIN_PHONE" in err and "SUPERADMIN_PASSWORD" in err
    assert secret not in err.replace("SUPERADMIN_", "")


def test_missing_config_without_admin_fails(db) -> None:
    assert bootstrap(db, _settings(superadmin_phone=None, superadmin_password=None)) == 1
    assert _super_admins(db) == []


def test_missing_config_ignored_when_admin_exists(db, make_user) -> None:
    make_user("super_admin")
    assert bootstrap(db, _settings(superadmin_phone=None, superadmin_password=None)) == 0
    assert len(_super_admins(db)) == 1
