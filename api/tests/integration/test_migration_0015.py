"""Migration 0015_notifications (specs/012 data-model.md › New table `notifications`)."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.conftest import API_ROOT
from tests.integration.test_migration_0014 import _INSERT_REQUEST

_ADD = (
    "INSERT INTO notifications (marketer_id, request_id, kind, reason, created_at) "
    "SELECT r.marketer_id, r.id, :kind, :reason, now() FROM requests r WHERE r.number = 1001"
)


def test_table_and_indexes_exist(engine) -> None:
    columns = {c["name"]: c for c in inspect(engine).get_columns("notifications")}
    assert set(columns) == {
        "id",
        "marketer_id",
        "request_id",
        "kind",
        "reason",
        "created_at",
        "read_at",
    }
    for required in ("id", "marketer_id", "request_id", "kind", "created_at"):
        assert columns[required]["nullable"] is False, required
    for optional in ("reason", "read_at"):
        assert columns[optional]["nullable"] is True, optional
    with engine.connect() as conn:
        names = set(
            conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'notifications'")
            ).scalars()
        )
    assert {"notifications_once", "notifications_marketer_id", "notifications_unread"} <= names


@pytest.fixture
def scratch_db(engine):
    """A fresh database at 0014 with one pending request, upgraded to head by the test."""
    url = engine.url.set(database=f"{engine.url.database}_mig15")
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "0014")
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (name, phone, password_hash, role, permissions) VALUES "
                "('مسوّق الترحيل', '07700000990', 'x', 'marketer', '[]')"
            )
        )
        conn.execute(text("INSERT INTO areas (name) VALUES ('منطقة')"))
        conn.execute(
            text(
                "INSERT INTO towers (code, name, area_id) "
                "SELECT 'MIG01', 'برج الترحيل', id FROM areas"
            )
        )
        conn.execute(text("INSERT INTO plans (name, trial_price, second_price) VALUES ('P', 1, 2)"))
        conn.execute(text(_INSERT_REQUEST), {"number": 1001})
    try:
        yield cfg, eng
    finally:
        eng.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        admin.dispose()


def _add(eng, kind: str, reason: str | None) -> None:
    with eng.begin() as conn:
        conn.execute(text(_ADD), {"kind": kind, "reason": reason})


def _refused(eng, kind: str, reason: str | None) -> None:
    with pytest.raises(IntegrityError):
        _add(eng, kind, reason)


def test_constraints_downgrade_and_upgrade_again(scratch_db) -> None:
    cfg, eng = scratch_db
    command.upgrade(cfg, "head")

    # Only the five kinds.
    _refused(eng, "seen", None)
    # No reason on approved / linked; a reason on rejected / deleted.
    _refused(eng, "approved", "other")
    _refused(eng, "linked", "other")
    _refused(eng, "rejected", None)
    _refused(eng, "deleted", None)

    # One per decision; linking may repeat (013).
    _add(eng, "approved", None)
    _refused(eng, "approved", None)
    _add(eng, "rejected", "other")
    _refused(eng, "rejected", "card_unclear")
    _add(eng, "deleted", "test")
    _refused(eng, "deleted", "test")
    _add(eng, "linked", None)
    _add(eng, "linked", None)
    _add(eng, "unlinked", "x")
    _add(eng, "unlinked", "x")

    # The marketer and the request are required.
    with pytest.raises(IntegrityError):
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO notifications (marketer_id, request_id, kind, created_at) "
                    "SELECT NULL, id, 'linked', now() FROM requests"
                )
            )

    command.downgrade(cfg, "0014")
    assert "notifications" not in inspect(eng).get_table_names()
    command.upgrade(cfg, "head")
    assert "notifications" in inspect(eng).get_table_names()
