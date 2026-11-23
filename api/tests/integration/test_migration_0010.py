"""Migration 0010_requests: constraints and a clean downgrade (specs/008 data-model.md)."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.models import RequestReason
from tests.conftest import API_ROOT
from tests.helpers.requests import request_factory


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


def _refused(db, **overrides) -> None:
    marketer = overrides.pop("_marketer")
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            request_factory(db, marketer, **overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "draft"},
        {"status": "cancelled"},
        {"type": "transfer"},
        {"phone": "7801234567"},
        {"national_id": "19901234567"},
        {"national_id": "١٩٩٠١٢٣٤٥٦٧٨"},
        {"family_key": "1234a"},
        {"family_key": "1234-A"},
        {"status": "approved", "approved_at": None},
        {"status": "pending_review", "approved_at": "2026-11-23T10:00:00Z"},
        {"no_surname": True},
    ],
    ids=lambda o: ",".join(f"{k}={v}" for k, v in o.items()),
)
def test_request_checks_refuse(db, marketer, overrides) -> None:
    _refused(db, _marketer=marketer, **overrides)


def test_number_and_draft_id_are_unique(db, marketer) -> None:
    first = request_factory(db, marketer)
    _refused(db, _marketer=marketer, number=first.number)
    _refused(db, _marketer=marketer, draft_id=first.draft_id)


def test_sequence_starts_at_1001(engine) -> None:
    with engine.connect() as conn:
        start = conn.execute(
            text("SELECT start_value FROM pg_sequences WHERE sequencename = 'request_number_seq'")
        ).scalar_one()
    assert start == 1001


def test_reason_check_and_unique_with_nulls(db, marketer) -> None:
    req = request_factory(db, marketer, status="pending_review")
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(RequestReason(request_id=req.id, reason="whatever"))
            db.flush()
    db.add(RequestReason(request_id=req.id, reason="numbers_edited", details={"fields": []}))
    db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(RequestReason(request_id=req.id, reason="numbers_edited", details={}))
            db.flush()


def test_downgrade_and_upgrade_again(engine) -> None:
    """On a separate database, so the shared test schema is untouched."""
    url = engine.url.set(database=f"{engine.url.database}_mig")
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
        command.downgrade(cfg, "0009")
        eng = create_engine(url)
        try:
            insp = inspect(eng)
            assert not {"requests", "request_reasons", "request_images"} & set(
                insp.get_table_names()
            )
            assert "additional_confirmed_key" not in {c["name"] for c in insp.get_columns("drafts")}
        finally:
            eng.dispose()
        command.upgrade(cfg, "head")
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        admin.dispose()
