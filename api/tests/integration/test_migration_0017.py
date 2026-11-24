"""Migration 0017_legacy_import (specs/014 data-model.md).

Tables legacy_imports, legacy_subscribers, legacy_images, legacy_import_previews, and the column
image_access_log.legacy_subscriber_id. Only synthetic values.
"""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.conftest import API_ROOT

_TABLES = ("legacy_imports", "legacy_subscribers", "legacy_images", "legacy_import_previews")


def test_tables_columns_and_indexes_exist(engine) -> None:
    insp = inspect(engine)
    assert set(_TABLES) <= set(insp.get_table_names())
    subs = {c["name"]: c for c in insp.get_columns("legacy_subscribers")}
    assert {
        "id",
        "import_id",
        "legacy_number",
        "form_submitted_at",
        "first_name",
        "second_name",
        "third_name",
        "full_name",
        "family_number_file",
        "family_number",
        "family_key",
        "phone",
        "phone_file",
        "status_text",
        "counts_in_check",
        "extra",
        "incomplete",
        "created_at",
    } == set(subs)
    for required in ("import_id", "legacy_number", "full_name", "counts_in_check", "extra"):
        assert subs[required]["nullable"] is False, required
    for optional in ("phone", "family_key", "family_number", "status_text", "form_submitted_at"):
        assert subs[optional]["nullable"] is True, optional
    previews = {c["name"] for c in insp.get_columns("legacy_import_previews")}
    assert {"id", "created_by", "created_at", "expires_at", "status", "rows"} <= previews
    log = {c["name"]: c for c in insp.get_columns("image_access_log")}
    assert log["legacy_subscriber_id"]["nullable"] is True
    with engine.connect() as conn:
        names = set(
            conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'legacy_subscribers'")
            ).scalars()
        )
    assert {"legacy_subscribers_phone", "legacy_subscribers_family_key"} <= names


@pytest.fixture
def scratch_db(engine):
    """A fresh database at head with one admin and one legacy import."""
    url = engine.url.set(database=f"{engine.url.database}_mig17")
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
                "('أدمن الترحيل', '07700000992', 'x', 'super_admin', '[]')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO legacy_imports (created_by, file_name, rows_total, imported, "
                "skipped, already_imported, not_counted, incomplete, corrected) "
                "SELECT id, 'legacy.csv', 0, 0, 0, 0, 0, 0, 0 FROM users"
            )
        )
    try:
        yield cfg, eng
    finally:
        eng.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        admin.dispose()


_SUB = (
    "INSERT INTO legacy_subscribers (import_id, legacy_number, full_name, phone, "
    "counts_in_check, incomplete) "
    "SELECT id, :number, 'اسم تجريبي', :phone, true, false FROM legacy_imports"
)
_IMG = (
    "INSERT INTO legacy_images (id, legacy_subscriber_id, side, file_name, size_bytes, width, "
    "height) SELECT :id, s.id, :side, :file, 10, 1, 1 FROM legacy_subscribers s "
    "WHERE s.legacy_number = 'T3C-001'"
)
_PREVIEW = (
    "INSERT INTO legacy_import_previews (id, created_by, expires_at, status, file_name, rows) "
    "SELECT :id, id, now(), :status, 'f.csv', '[]' FROM users"
)


def _run(eng, sql: str, **params) -> None:
    with eng.begin() as conn:
        conn.execute(text(sql), params)


def _refused(eng, sql: str, **params) -> None:
    with pytest.raises(IntegrityError):
        _run(eng, sql, **params)


def test_constraints_downgrade_and_upgrade_again(scratch_db) -> None:
    cfg, eng = scratch_db

    # legacy_number: shape T3C-ddd, unique.
    for bad in ("T3C-1", "t3c-001", "T3C-0001", "X-001"):
        _refused(eng, _SUB, number=bad, phone=None)
    _run(eng, _SUB, number="T3C-001", phone="07801234567")
    _refused(eng, _SUB, number="T3C-001", phone=None)
    # phone: §8.1 shape or NULL.
    _refused(eng, _SUB, number="T3C-002", phone="7801234567")
    _run(eng, _SUB, number="T3C-002", phone=None)

    # legacy_images: front/back only, one per side.
    _refused(eng, _IMG, id=uuid.uuid4(), side="left", file="a" * 32 + ".jpg")
    _run(eng, _IMG, id=uuid.uuid4(), side="front", file="b" * 32 + ".jpg")
    _refused(eng, _IMG, id=uuid.uuid4(), side="front", file="c" * 32 + ".jpg")
    _run(eng, _IMG, id=uuid.uuid4(), side="back", file="d" * 32 + ".jpg")

    # previews: three statuses.
    _refused(eng, _PREVIEW, id=uuid.uuid4(), status="done")
    for status in ("fetching", "ready", "failed"):
        _run(eng, _PREVIEW, id=uuid.uuid4(), status=status)

    command.downgrade(cfg, "0016")
    insp = inspect(eng)
    assert not set(_TABLES) & set(insp.get_table_names())
    assert "legacy_subscriber_id" not in {c["name"] for c in insp.get_columns("image_access_log")}
    command.upgrade(cfg, "head")
    assert set(_TABLES) <= set(inspect(eng).get_table_names())
