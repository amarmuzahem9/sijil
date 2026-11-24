"""Migration 0016_request_links (specs/013 data-model.md).

`requests.linked_at` / `requests.linked_by` with their checks, the append-only `request_links`
table, and the `notifications_reason_kind` check that now needs a reason on `unlinked`.
"""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.conftest import API_ROOT
from tests.integration.test_migration_0014 import _INSERT_REQUEST

_REQ = "(SELECT id FROM requests WHERE number = 1001)"
_ADMIN = "(SELECT id FROM users WHERE role = 'super_admin')"


def test_columns_table_and_indexes_exist(engine) -> None:
    insp = inspect(engine)
    req = {c["name"]: c for c in insp.get_columns("requests")}
    assert req["linked_at"]["nullable"] is True
    assert req["linked_by"]["nullable"] is True
    links = {c["name"]: c for c in insp.get_columns("request_links")}
    assert set(links) == {"id", "request_id", "kind", "actor_id", "at", "reason"}
    for required in ("id", "request_id", "kind", "actor_id", "at"):
        assert links[required]["nullable"] is False, required
    assert links["reason"]["nullable"] is True
    with engine.connect() as conn:
        names = set(
            conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename IN ('requests', 'request_links')"
                )
            ).scalars()
        )
    assert {
        "requests_awaiting_link",
        "requests_linked_at",
        "requests_linked_recent",
        "request_links_request",
    } <= names


@pytest.fixture
def scratch_db(engine):
    """A fresh database at 0015 with one pending request and a main admin."""
    url = engine.url.set(database=f"{engine.url.database}_mig16")
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "0015")
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (name, phone, password_hash, role, permissions) VALUES "
                "('مسوّق الترحيل', '07700000991', 'x', 'marketer', '[]'), "
                "('أدمن الترحيل', '07700000992', 'x', 'super_admin', '[]')"
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


_SET = (
    "UPDATE requests SET status = :status, "
    "approved_at = CASE WHEN :approved THEN now() END, "
    "linked_at = CASE WHEN :linked_at THEN now() END, "
    "linked_by = CASE WHEN :linked_by THEN (SELECT id FROM users WHERE role = 'super_admin') END "
    "WHERE number = 1001"
)
_LINK_ROW = (
    "INSERT INTO request_links (request_id, kind, actor_id, at, reason) "
    "VALUES (" + _REQ + ", :kind, " + _ADMIN + ", now(), :reason)"
)
_NOTIFY = (
    "INSERT INTO notifications (marketer_id, request_id, kind, reason, created_at) "
    "SELECT r.marketer_id, r.id, 'unlinked', :reason, now() FROM requests r "
    "WHERE r.number = 1001"
)


def _run(eng, sql: str, **params) -> None:
    with eng.begin() as conn:
        conn.execute(text(sql), params)


def _refused(eng, sql: str, **params) -> None:
    with pytest.raises(IntegrityError):
        _run(eng, sql, **params)


def _set(status: str, approved: bool, linked_at: bool, linked_by: bool | None = None) -> dict:
    return {
        "status": status,
        "approved": approved,
        "linked_at": linked_at,
        "linked_by": linked_at if linked_by is None else linked_by,
    }


def test_constraints_downgrade_and_upgrade_again(scratch_db) -> None:
    cfg, eng = scratch_db
    command.upgrade(cfg, "head")

    # requests_linked_has_time: linked ⇔ linked_at and linked_by.
    _refused(eng, _SET, **_set("linked", approved=True, linked_at=False))
    _refused(eng, _SET, **_set("approved", approved=True, linked_at=True))
    _refused(eng, _SET, **_set("linked", approved=True, linked_at=True, linked_by=False))
    # requests_linked_approved: a linked request was accepted.
    _refused(eng, _SET, **_set("linked", approved=False, linked_at=True))
    _run(eng, _SET, **_set("linked", approved=True, linked_at=True))
    _run(eng, _SET, **_set("approved", approved=True, linked_at=False))

    # request_links: two kinds; no reason on a link; one of four reasons on an undo.
    _refused(eng, _LINK_ROW, kind="seen", reason=None)
    _refused(eng, _LINK_ROW, kind="linked", reason="by_mistake")
    _refused(eng, _LINK_ROW, kind="unlinked", reason=None)
    _refused(eng, _LINK_ROW, kind="unlinked", reason="free text")
    _run(eng, _LINK_ROW, kind="linked", reason=None)
    for code in ("not_linked_in_sas", "by_mistake", "other_request_linked", "other"):
        _run(eng, _LINK_ROW, kind="unlinked", reason=code)
    _refused(
        eng,
        "INSERT INTO request_links (request_id, kind, actor_id, at) "
        "VALUES (NULL, 'linked', " + _ADMIN + ", now())",
    )
    _refused(
        eng,
        "INSERT INTO request_links (request_id, kind, actor_id, at) "
        "VALUES (" + _REQ + ", 'linked', NULL, now())",
    )

    # notifications_reason_kind: `unlinked` needs a reason now.
    _refused(eng, _NOTIFY, reason=None)
    _run(eng, _NOTIFY, reason="by_mistake")

    # Downgrade removes all of it (the rows go first: 0015 refuses nothing it knew).
    command.downgrade(cfg, "0015")
    insp = inspect(eng)
    assert "request_links" not in insp.get_table_names()
    assert "linked_at" not in {c["name"] for c in insp.get_columns("requests")}
    command.upgrade(cfg, "head")
    assert "request_links" in inspect(eng).get_table_names()
