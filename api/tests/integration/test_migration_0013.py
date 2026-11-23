"""Migration 0013_admin_review (specs/010 data-model.md): decision columns, submitted values,
reason state, number pins and request image access."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.conftest import API_ROOT

_INSERT_REQUEST = (
    "INSERT INTO requests (number, draft_id, marketer_id, type, status, "
    "first_name, father_name, grandfather_name, great_grandfather_name, "
    "surname, mother_first_name, mother_second_name, full_name, no_surname, "
    "national_id, national_id_input, family_number, family_key, birth_date, "
    "issue_date, expiry_date, birth_place, issuing_authority, card_fields, "
    "card_readings, location_lat, location_lng, location_source, address, "
    "landmark, area_id, tower_id, plan_id, area_name, tower_code, tower_name, plan_name, "
    "trial_price, second_price, phone, username, otp_verified_at, submitted_at) "
    "SELECT :number, gen_random_uuid(), u.id, 'new', 'pending_review', "
    "'ا','ب','ج','د','ه','و','ز','ا ب ج د ه', false, '199000000001', "
    "'١٩٩٠٠٠٠٠٠٠٠١', '1234a-5678', '1234A5678', '1990-01-01', '2020-01-01', '2030-01-01', "
    "'بغداد', 'جهة', '{}', '{}', 33.3, 44.3, 'gps', 'عنوان', 'نقطة', "
    "a.id, t.id, p.id, 'منطقة', 'MIG01', 'برج', 'P', 1, 2, '07800000990', "
    "'MIG01-07800000990', now(), now() "
    "FROM users u, areas a, towers t, plans p"
)


def _columns(engine, table: str) -> dict:
    return {c["name"]: c for c in inspect(engine).get_columns(table)}


def test_columns_exist(engine) -> None:
    req = _columns(engine, "requests")
    assert req["counts_commission"]["nullable"] is False
    # Required from 0013; nullable from 0014, where `requests_erasure` keeps them required on
    # every live row (specs/011 data-model.md).
    for name in ("submitted_national_id", "submitted_family_number"):
        assert name in req
    for name in (
        "approval_warnings",
        "rejected_at",
        "rejected_by",
        "rejection_reason",
        "rejection_note",
    ):
        assert req[name]["nullable"] is True
    reasons = _columns(engine, "request_reasons")
    assert reasons["state"]["nullable"] is False
    for name in ("state_changed_at", "state_changed_by", "added_by"):
        assert reasons[name]["nullable"] is True
    pins = _columns(engine, "request_number_pins")
    for name in (
        "request_id",
        "field",
        "previous_value",
        "value",
        "source",
        "pinned_by",
        "pinned_at",
    ):
        assert pins[name]["nullable"] is False
    log = _columns(engine, "image_access_log")
    assert log["draft_id"]["nullable"] is True
    assert log["request_id"]["nullable"] is True
    indexes = {i["name"] for i in inspect(engine).get_indexes("requests")}
    assert "requests_pending_idx" in indexes


@pytest.fixture
def scratch_db(engine):
    """A fresh database at 0012 with one pending request, upgraded to head by the test."""
    url = engine.url.set(database=f"{engine.url.database}_mig13")
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "0012")
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (name, phone, password_hash, role, permissions) "
                "VALUES ('مسوّق الترحيل', '07700000990', 'x', 'marketer', '[]')"
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


def _refused(eng, sql: str) -> None:
    with pytest.raises(IntegrityError):
        with eng.begin() as conn:
            conn.execute(text(sql))


def test_backfill_constraints_downgrade_and_upgrade_again(scratch_db) -> None:
    cfg, eng = scratch_db
    command.upgrade(cfg, "head")

    with eng.connect() as conn:
        row = conn.execute(
            text(
                "SELECT submitted_national_id, submitted_family_number, counts_commission "
                "FROM requests"
            )
        ).one()
    # The marketer's values as written: national_id_input and family_number.
    assert row == ("١٩٩٠٠٠٠٠٠٠٠١", "1234a-5678", True)

    # A rejected request needs its time, admin and reason.
    _refused(eng, "UPDATE requests SET status = 'rejected'")
    # «سبب آخر» needs a note; any other reason refuses one; unknown codes are refused.
    base = (
        "UPDATE requests SET status = 'rejected', rejected_at = now(), "
        "rejected_by = (SELECT id FROM users LIMIT 1), "
    )
    _refused(eng, base + "rejection_reason = 'other'")
    _refused(eng, base + "rejection_reason = 'card_unclear', rejection_note = 'نص'")
    _refused(eng, base + "rejection_reason = 'unknown'")
    with eng.begin() as conn:
        conn.execute(text(base + "rejection_reason = 'other', rejection_note = 'طلب مكرر'"))
    # A rejected request has no approval time.
    _refused(eng, "UPDATE requests SET approved_at = now()")

    # Reason state is one of three values.
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO request_reasons (request_id, reason, details) "
                "SELECT id, 'numbers_edited', '{}' FROM requests"
            )
        )
        assert conn.execute(text("SELECT state FROM request_reasons")).scalar_one() == "open"
    _refused(eng, "UPDATE request_reasons SET state = 'closed'")

    # Pins: `mrz` only for the national ID.
    pin = (
        "INSERT INTO request_number_pins "
        "(request_id, field, previous_value, value, source, pinned_by, pinned_at) "
        "SELECT r.id, '{field}', 'x', 'y', '{source}', u.id, now() FROM requests r, users u"
    )
    _refused(eng, pin.format(field="family_number", source="mrz"))
    _refused(eng, pin.format(field="names", source="typed"))
    _refused(eng, pin.format(field="national_id", source="guess"))
    with eng.begin() as conn:
        conn.execute(text(pin.format(field="national_id", source="mrz")))

    # Image access may name a request instead of a draft.
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO image_access_log (user_id, image_id, request_id, side) "
                "SELECT u.id, gen_random_uuid(), r.id, 'front' FROM users u, requests r"
            )
        )

    # A downgrade would destroy the decision and the pin: it is refused.
    with pytest.raises(RuntimeError, match="0013 downgrade refused"):
        command.downgrade(cfg, "0012")

    # Without review data (this scratch database only), it round-trips.
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM request_number_pins"))
        conn.execute(
            text(
                "UPDATE requests SET status = 'pending_review', rejected_at = NULL, "
                "rejected_by = NULL, rejection_reason = NULL, rejection_note = NULL"
            )
        )
    command.downgrade(cfg, "0012")
    assert "request_number_pins" not in inspect(eng).get_table_names()
    with eng.connect() as conn:
        # The request image open kept its draft id.
        assert (
            conn.execute(
                text("SELECT count(*) FROM image_access_log WHERE draft_id IS NOT NULL")
            ).scalar_one()
            == 1
        )
    command.upgrade(cfg, "head")
