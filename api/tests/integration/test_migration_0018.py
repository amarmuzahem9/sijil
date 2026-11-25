"""Migration 0018_sas_import (specs/015 data-model.md).

Tables sas_imports, sas_subscribers, sas_subscriber_changes, sas_tower_mappings and
sas_import_previews. Only synthetic values; no column may ever hold a password (research R3).
"""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.conftest import API_ROOT

_TABLES = (
    "sas_imports",
    "sas_subscribers",
    "sas_subscriber_changes",
    "sas_tower_mappings",
    "sas_import_previews",
)


def test_tables_columns_and_indexes_exist(engine) -> None:
    insp = inspect(engine)
    assert set(_TABLES) <= set(insp.get_table_names())
    subs = {c["name"]: c for c in insp.get_columns("sas_subscribers")}
    assert {
        "id",
        "username",
        "username_key",
        "sas_id",
        "first_name",
        "last_name",
        "full_name",
        "phone",
        "phone_file",
        "username_phone",
        "tower_prefix",
        "tower_id",
        "expires_at",
        "sas_created_at",
        "last_online_at",
        "group_name",
        "parent_name",
        "notes",
        "first_import_id",
        "last_import_id",
        "missing_since",
        "missing_import_id",
        "created_at",
        "updated_at",
    } == set(subs)
    for required in ("username", "username_key", "full_name", "first_import_id", "last_import_id"):
        assert subs[required]["nullable"] is False, required
    for optional in ("phone", "username_phone", "tower_id", "expires_at", "missing_since"):
        assert subs[optional]["nullable"] is True, optional
    imports = {c["name"] for c in insp.get_columns("sas_imports")}
    assert {
        "id",
        "created_by",
        "created_at",
        "file_name",
        "rows_total",
        "added",
        "updated",
        "unchanged",
        "skipped",
        "missing_marked",
        "missing_cleared",
        "without_phone",
        "prefixes_mapped",
    } == imports
    changes = {c["name"] for c in insp.get_columns("sas_subscriber_changes")}
    assert {"id", "import_id", "sas_subscriber_id", "before", "after", "created_at"} == changes
    mappings = {c["name"]: c for c in insp.get_columns("sas_tower_mappings")}
    assert {"prefix", "tower_id", "set_by", "set_at", "import_id"} == set(mappings)
    assert mappings["tower_id"]["nullable"] is True
    assert insp.get_pk_constraint("sas_tower_mappings")["constrained_columns"] == ["prefix"]
    previews = {c["name"] for c in insp.get_columns("sas_import_previews")}
    assert {
        "id",
        "created_by",
        "created_at",
        "expires_at",
        "file_name",
        "rows",
        "prefixes",
        "missing_ids",
    } == previews
    for table in _TABLES:
        for column in insp.get_columns(table):
            assert "password" not in column["name"].lower(), (table, column["name"])
    with engine.connect() as conn:
        names = set(
            conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename = 'sas_subscribers'")
            ).scalars()
        )
    assert {"sas_subscribers_phone", "sas_subscribers_username_phone"} <= names


@pytest.fixture
def scratch_db(engine):
    """A fresh database at head with one admin, one area, two towers and one SAS import."""
    url = engine.url.set(database=f"{engine.url.database}_mig18")
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
                "('أدمن الترحيل', '07700000993', 'x', 'super_admin', '[]')"
            )
        )
        conn.execute(text("INSERT INTO areas (name) VALUES ('منطقة تجريبية')"))
        conn.execute(
            text(
                "INSERT INTO towers (area_id, code, name) SELECT id, c, 'برج ' || c "
                "FROM areas, (VALUES ('ZZT01'), ('ZZT02')) AS v(c)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO sas_imports (created_by, file_name, rows_total, added, updated, "
                "unchanged, skipped, missing_marked, missing_cleared, without_phone, "
                "prefixes_mapped) SELECT id, 'sas.csv', 0, 0, 0, 0, 0, 0, 0, 0, 0 FROM users"
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
    "INSERT INTO sas_subscribers (username, username_key, full_name, phone, username_phone, "
    "tower_id, first_import_id, last_import_id) "
    "SELECT :username, upper(:username), 'اسم تجريبي', :phone, :uphone, "
    "(SELECT id FROM towers WHERE code = :tower), id, id FROM sas_imports"
)
_MAP = (
    "INSERT INTO sas_tower_mappings (prefix, tower_id, set_by, import_id) "
    "SELECT :prefix, (SELECT id FROM towers WHERE code = :tower), created_by, id FROM sas_imports"
)
_PREVIEW = (
    "INSERT INTO sas_import_previews (id, created_by, expires_at, file_name, rows, prefixes, "
    "missing_ids) SELECT :id, id, now(), 'f.csv', '[]', '[]', '[]' FROM users"
)


def _run(eng, sql: str, **params) -> None:
    with eng.begin() as conn:
        conn.execute(text(sql), params)


def _refused(eng, sql: str, **params) -> None:
    with pytest.raises(IntegrityError):
        _run(eng, sql, **params)


def test_constraints_downgrade_and_upgrade_again(scratch_db) -> None:
    cfg, eng = scratch_db
    sub = {"phone": None, "uphone": None, "tower": None}

    # username_key unique.
    _run(eng, _SUB, username="ZZT01-07801234567", **sub)
    _refused(eng, _SUB, username="zzt01-07801234567", **sub)
    # phone and username_phone: §8.1 shape or NULL.
    _refused(eng, _SUB, username="A-1", **(sub | {"phone": "7801234567"}))
    _refused(eng, _SUB, username="A-2", **(sub | {"uphone": "07801"}))
    _run(eng, _SUB, username="A-3", **(sub | {"phone": "07801234567", "uphone": "07709999999"}))

    # prefix is the primary key; «بلا برج» is a NULL tower.
    _run(eng, _MAP, prefix="OLD-1", tower="ZZT02")
    _refused(eng, _MAP, prefix="OLD-1", tower=None)
    _run(eng, _MAP, prefix="GONE", tower=None)

    # A tower used by a SAS subscriber or a mapping cannot be deleted.
    _run(eng, _SUB, username="ZZT01-07701111111", **(sub | {"tower": "ZZT01"}))
    _refused(eng, "DELETE FROM towers WHERE code = 'ZZT01'")
    _refused(eng, "DELETE FROM towers WHERE code = 'ZZT02'")

    _run(eng, _PREVIEW, id=uuid.uuid4())

    command.downgrade(cfg, "0017")
    assert not set(_TABLES) & set(inspect(eng).get_table_names())
    command.upgrade(cfg, "head")
    assert set(_TABLES) <= set(inspect(eng).get_table_names())
