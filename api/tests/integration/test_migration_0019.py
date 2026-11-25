"""Migration 0019_backups (specs/016 data-model.md «Tables (mirror)»).

backup_runs, backup_events and backup_status mirror the backup files for the main admin's page.
No column holds personal data, a path to a card image, or a key.
"""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.conftest import API_ROOT

_TABLES = ("backup_runs", "backup_events", "backup_status")


def test_tables_and_columns(engine) -> None:
    insp = inspect(engine)
    assert set(_TABLES) <= set(insp.get_table_names())
    runs = {c["name"]: c for c in insp.get_columns("backup_runs")}
    assert {
        "id",
        "snapshot_id",
        "kind",
        "status",
        "error_code",
        "requested_by",
        "started_at",
        "finished_at",
        "total_size",
        "image_count",
        "counts",
        "removed_at",
        "created_at",
    } == set(runs)
    for required in ("id", "kind", "status", "created_at"):
        assert runs[required]["nullable"] is False, required
    for optional in ("snapshot_id", "error_code", "requested_by", "started_at", "counts"):
        assert runs[optional]["nullable"] is True, optional
    events = {c["name"]: c for c in insp.get_columns("backup_events")}
    assert {"id", "type", "at", "result", "snapshot_id", "details"} == set(events)
    status = {c["name"] for c in insp.get_columns("backup_status")}
    assert {
        "id",
        "heartbeat_at",
        "free_bytes",
        "total_bytes",
        "min_free_bytes",
        "nightly_at",
        "external_dir",
        "backup_dir_bytes",
        "key_configured",
    } == status
    for table in _TABLES:
        for column in insp.get_columns(table):
            assert not any(
                word in column["name"] for word in ("password", "secret", "passphrase", "phone")
            ), (table, column["name"])


@pytest.fixture
def scratch_db(engine):
    """A fresh database at head with one main admin."""
    url = engine.url.set(database=f"{engine.url.database}_mig19")
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
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (name, phone, password_hash, role, permissions) VALUES "
                "('أدمن الترحيل', '07700000994', 'x', 'super_admin', '[]')"
            )
        )
    try:
        yield cfg, eng
    finally:
        eng.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        admin.dispose()


_RUN = (
    "INSERT INTO backup_runs (id, snapshot_id, kind, status, error_code, requested_by) "
    "VALUES (:id, :snap, :kind, :status, :err, (SELECT id FROM users LIMIT 1))"
)
_EVENT = (
    "INSERT INTO backup_events (id, type, at, result, details) "
    "VALUES (:id, :type, now(), :result, '{}')"
)
_STATUS = "INSERT INTO backup_status (id, nightly_at) VALUES (:id, '03:00')"


def _run(eng, sql: str, **params) -> None:
    with eng.begin() as conn:
        conn.execute(text(sql), params)


def _refused(eng, sql: str, **params) -> None:
    with pytest.raises(IntegrityError):
        _run(eng, sql, **params)


def _row(**over):
    base = {"id": "r", "snap": None, "kind": "nightly", "status": "succeeded", "err": None}
    return base | over


def test_constraints_downgrade_and_upgrade_again(scratch_db) -> None:
    cfg, eng = scratch_db

    # kind, status and error_code lists (data-model.md backup_runs).
    _run(eng, _RUN, **_row(id="a", snap="20261125-000000-nightly"))
    _refused(eng, _RUN, **_row(id="b", kind="weekly"))
    _refused(eng, _RUN, **_row(id="c", status="done"))
    _refused(eng, _RUN, **_row(id="d", status="failed", err="oops"))
    _run(eng, _RUN, **_row(id="e", status="failed", err="disk_low"))

    # snapshot_id is unique but NULL on several rows.
    _refused(eng, _RUN, **_row(id="f", snap="20261125-000000-nightly"))
    _run(eng, _RUN, **_row(id="g", kind="manual", status="failed", err="busy"))
    _run(eng, _RUN, **_row(id="h", kind="manual", status="failed", err="internal"))

    # Only one run requested or running at a time.
    _run(eng, _RUN, **_row(id="req-1", kind="manual", status="requested"))
    _refused(eng, _RUN, **_row(id="req-2", kind="manual", status="requested"))
    _refused(eng, _RUN, **_row(id="i", status="running"))
    _run(
        eng,
        "UPDATE backup_runs SET status = 'failed', error_code = 'internal' WHERE id = 'req-1'",
    )
    _run(eng, _RUN, **_row(id="j", status="running"))

    # backup_events type and result lists.
    _run(eng, _EVENT, id="e1", type="drill", result="passed")
    _run(eng, _EVENT, id="e2", type="external_copy", result="succeeded")
    _refused(eng, _EVENT, id="e3", type="upload", result="passed")
    _refused(eng, _EVENT, id="e4", type="drill", result="ok")

    # backup_status is a single row, id = 1.
    _run(eng, _STATUS, id=1)
    _refused(eng, _STATUS, id=2)

    command.downgrade(cfg, "0018")
    assert not set(_TABLES) & set(inspect(eng).get_table_names())
    command.upgrade(cfg, "head")
    assert set(_TABLES) <= set(inspect(eng).get_table_names())
