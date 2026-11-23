"""Migration 0011_existing_subscriber_paths (specs/009 data-model.md)."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.models import RequestReason
from tests.conftest import API_ROOT
from tests.helpers.requests import request_factory


def test_drafts_have_return_key(engine) -> None:
    columns = {c["name"]: c for c in inspect(engine).get_columns("drafts")}
    assert "return_key" in columns
    assert columns["return_key"]["nullable"] is True


def test_reason_check_accepts_numbers_conflict(db, make_user) -> None:
    req = request_factory(db, make_user("marketer"), status="pending_review")
    db.add(
        RequestReason(
            request_id=req.id, reason="numbers_conflict", matched_source="sijil", matched_ref="1"
        )
    )
    db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(RequestReason(request_id=req.id, reason="whatever"))
            db.flush()


def test_downgrade_and_upgrade_again(engine) -> None:
    """On a separate database, so the shared test schema is untouched."""
    url = engine.url.set(database=f"{engine.url.database}_mig11")
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    try:
        cfg = Config(str(API_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
        cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
        cfg.attributes["configure_logger"] = False
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "0010")
        eng = create_engine(url)
        try:
            assert "return_key" not in {c["name"] for c in inspect(eng).get_columns("drafts")}
            with eng.connect() as conn:
                definition = conn.execute(
                    text(
                        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                        "WHERE conname = 'request_reasons_reason'"
                    )
                ).scalar_one()
            assert "numbers_conflict" not in definition
        finally:
            eng.dispose()
        command.upgrade(cfg, "head")
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        admin.dispose()
