"""Migration 0021_exports (specs/019 data-model.md).

exports: one row per requests export, its state and times checked, one `preparing` per admin.
image_access_log.purpose: widened with `export` (analysis C1).
requests_submitted_at_idx: the submission-date filter (research R3).
"""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.conftest import API_ROOT

_COLUMNS = {
    "id",
    "requester_id",
    "filters",
    "include_identity",
    "state",
    "row_count",
    "missing_images",
    "error_code",
    "ticket_hash",
    "ticket_expires_at",
    "created_at",
    "ready_at",
    "expires_at",
    "removed_at",
}
_REQUIRED = {"id", "requester_id", "filters", "include_identity", "state", "created_at"}


def test_head_is_0021(engine) -> None:
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0021"


def test_columns(engine) -> None:
    insp = inspect(engine)
    cols = {c["name"]: c for c in insp.get_columns("exports")}
    assert set(cols) == _COLUMNS
    for name, column in cols.items():
        assert column["nullable"] is (name not in _REQUIRED), name


def test_indexes(engine) -> None:
    insp = inspect(engine)
    assert {"exports_one_preparing", "exports_requester_created"} <= {
        i["name"] for i in insp.get_indexes("exports")
    }
    assert "requests_submitted_at_idx" in {i["name"] for i in insp.get_indexes("requests")}


_INSERT = (
    "INSERT INTO exports (id, requester_id, filters, include_identity, state, created_at, "
    "ready_at, expires_at, removed_at) VALUES (:id, :u, '{}'::jsonb, false, :state, now(), "
    ":ready, :expires, :removed)"
)


def _insert(conn, user_id: int, state: str, ready=None, expires=None, removed=None) -> None:
    conn.execute(
        text(_INSERT),
        {
            "id": uuid.uuid4(),
            "u": user_id,
            "state": state,
            "ready": ready,
            "expires": expires,
            "removed": removed,
        },
    )


_T = "2026-11-27T10:00:00+00:00"
_T24 = "2026-11-28T10:00:00+00:00"


@pytest.mark.parametrize(
    ("state", "ready", "expires", "removed"),
    [
        ("other", None, None, None),  # unknown state
        ("ready", None, _T24, None),  # ready without ready_at
        ("ready", _T, None, None),  # ready without expires_at
        ("ready", _T, _T24, _T24),  # ready but removed
        ("preparing", _T, _T24, None),  # ready times on a row that is not ready
    ],
)
def test_state_checks(db, make_user, state, ready, expires, removed) -> None:
    admin = make_user(role="super_admin")
    with pytest.raises(IntegrityError), db.begin_nested():
        _insert(db, admin.id, state, ready, expires, removed)


def test_valid_states(db, make_user) -> None:
    admin = make_user(role="super_admin")
    _insert(db, admin.id, "ready", _T, _T24)
    _insert(db, admin.id, "failed")
    _insert(db, admin.id, "removed", _T, _T24, _T24)  # a removed row keeps ready_at
    _insert(db, admin.id, "removed")
    _insert(db, admin.id, "preparing")


def test_created_at_required(db, make_user) -> None:
    admin = make_user(role="super_admin")
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO exports (id, requester_id, filters, include_identity, state, "
                "created_at) VALUES (:id, :u, '{}'::jsonb, false, 'preparing', NULL)"
            ),
            {"id": uuid.uuid4(), "u": admin.id},
        )


def test_one_preparing_per_requester(db, make_user) -> None:
    first = make_user(role="super_admin")
    second = make_user(role="admin")
    _insert(db, first.id, "preparing")
    _insert(db, second.id, "preparing")  # another requester: allowed
    _insert(db, first.id, "ready", _T, _T24)  # not preparing: allowed
    with pytest.raises(IntegrityError), db.begin_nested():
        _insert(db, first.id, "preparing")


_ACCESS = (
    "INSERT INTO image_access_log (user_id, image_id, side, purpose) "
    "VALUES (:u, :img, 'front', :purpose)"
)


def test_image_access_purpose_export(db, make_user) -> None:
    admin = make_user(role="super_admin")
    db.execute(text(_ACCESS), {"u": admin.id, "img": uuid.uuid4(), "purpose": "export"})
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text(_ACCESS), {"u": admin.id, "img": uuid.uuid4(), "purpose": "other"})


@pytest.fixture
def scratch_db(engine):
    """A fresh database at head."""
    url = engine.url.set(database=f"{engine.url.database}_mig21")
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    try:
        yield cfg, eng
    finally:
        eng.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        admin.dispose()


def test_downgrade_and_upgrade_again(scratch_db) -> None:
    cfg, eng = scratch_db
    assert "exports" in inspect(eng).get_table_names()
    command.downgrade(cfg, "0020")
    insp = inspect(eng)
    assert "exports" not in insp.get_table_names()
    assert "requests_submitted_at_idx" not in {i["name"] for i in insp.get_indexes("requests")}
    command.upgrade(cfg, "head")
    assert "exports" in inspect(eng).get_table_names()


def test_downgrade_refused_with_export_access_rows(scratch_db) -> None:
    """Access rows are never deleted (analysis C1), so the downgrade stops instead."""
    cfg, eng = scratch_db
    with eng.begin() as conn:
        user_id = conn.execute(
            text(
                "INSERT INTO users (phone, name, password_hash, role) "
                "VALUES ('07710009999', 'اختبار', 'x', 'super_admin') RETURNING id"
            )
        ).scalar_one()
        conn.execute(text(_ACCESS), {"u": user_id, "img": uuid.uuid4(), "purpose": "export"})
    with pytest.raises(Exception, match="export"):
        command.downgrade(cfg, "0020")
    with eng.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM image_access_log")).scalar_one() == 1
