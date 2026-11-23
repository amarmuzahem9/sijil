"""Migration 0014_subscriber_deletion (specs/011 data-model.md): the deletion mark, the personal
columns made nullable, the erasure checks, the pending index and the `delete` permission."""

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
    "national_id, national_id_input, submitted_national_id, family_number, "
    "submitted_family_number, family_key, birth_date, "
    "issue_date, expiry_date, birth_place, issuing_authority, card_fields, "
    "card_readings, location_lat, location_lng, location_source, address, "
    "landmark, area_id, tower_id, plan_id, area_name, tower_code, tower_name, plan_name, "
    "trial_price, second_price, phone, username, otp_verified_at, submitted_at) "
    "SELECT :number, gen_random_uuid(), u.id, 'new', 'pending_review', "
    "'ا','ب','ج','د','ه','و','ز','ا ب ج د ه', false, '199000000001', "
    "'١٩٩٠٠٠٠٠٠٠٠١', '١٩٩٠٠٠٠٠٠٠٠١', '1234a-5678', '1234a-5678', '1234A5678', "
    "'1990-01-01', '2020-01-01', '2030-01-01', "
    "'بغداد', 'جهة', '{}', '{}', 33.3, 44.3, 'gps', 'عنوان', 'نقطة', "
    "a.id, t.id, p.id, 'منطقة', 'MIG01', 'برج', 'P', 1, 2, '07800000990', "
    "'MIG01-07800000990', now(), now() "
    "FROM users u, areas a, towers t, plans p WHERE u.role = 'marketer'"
)

# data-model.md › requests: every column a deletion sets to NULL.
ERASED = (
    "first_name",
    "father_name",
    "grandfather_name",
    "great_grandfather_name",
    "surname",
    "mother_first_name",
    "mother_second_name",
    "mother_third_name",
    "mother_surname",
    "full_name",
    "no_surname",
    "national_id",
    "national_id_input",
    "submitted_national_id",
    "family_number",
    "submitted_family_number",
    "family_key",
    "birth_date",
    "issue_date",
    "expiry_date",
    "birth_place",
    "issuing_authority",
    "card_fields",
    "national_id_check",
    "card_readings",
    "location_lat",
    "location_lng",
    "location_source",
    "location_accuracy_m",
    "address",
    "landmark",
    "phone",
    "username",
    "rejection_note",
)
MADE_NULLABLE = tuple(
    c
    for c in ERASED
    if c
    not in (
        "surname",
        "mother_third_name",
        "mother_surname",
        "national_id_check",
        "location_accuracy_m",
        "rejection_note",
    )
)


def _mark(reason: str = "test", keep: tuple[str, ...] = ()) -> str:
    nulls = ", ".join(f"{c} = NULL" for c in ERASED if c not in keep)
    # Column names and reasons are constants of this test, never input.
    return (
        f"UPDATE requests SET {nulls}, deleted_at = now(), "  # noqa: S608
        f"deleted_by = (SELECT id FROM users WHERE role = 'super_admin'), "
        f"deletion_reason = '{reason}'"
    )


def _columns(engine, table: str) -> dict:
    return {c["name"]: c for c in inspect(engine).get_columns(table)}


def test_columns_exist(engine) -> None:
    req = _columns(engine, "requests")
    for name in ("deleted_at", "deleted_by", "deletion_reason", *MADE_NULLABLE):
        assert req[name]["nullable"] is True, name
    with engine.connect() as conn:
        indexdef = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'requests_pending_idx'")
        ).scalar_one()
    assert "deleted_at IS NULL" in indexdef


@pytest.fixture
def scratch_db(engine):
    """A fresh database at 0013 with one pending request, upgraded to head by the test."""
    url = engine.url.set(database=f"{engine.url.database}_mig14")
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "0013")
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (name, phone, password_hash, role, permissions) VALUES "
                "('مسوّق الترحيل', '07700000990', 'x', 'marketer', '[]'), "
                "('أدمن الترحيل', '07700000991', 'x', 'super_admin', '[]')"
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


def test_constraints_downgrade_and_upgrade_again(scratch_db) -> None:
    cfg, eng = scratch_db
    command.upgrade(cfg, "head")

    # A live row keeps its required personal columns.
    _refused(eng, "UPDATE requests SET phone = NULL")
    _refused(eng, "UPDATE requests SET full_name = NULL")
    # The mark is all three columns or none.
    _refused(eng, "UPDATE requests SET deleted_at = now()")
    _refused(eng, _mark().replace(", deletion_reason = 'test'", ""))
    # Only the four reasons.
    _refused(eng, _mark("guess"))
    # A marked row holds no personal value.
    _refused(eng, _mark(keep=("phone",)))
    _refused(eng, _mark(keep=("national_id",)))

    # An approved request cannot carry a mark.
    with eng.begin() as conn:
        conn.execute(text("UPDATE requests SET status = 'approved', approved_at = now()"))
    _refused(eng, _mark())
    with eng.begin() as conn:
        conn.execute(text("UPDATE requests SET status = 'pending_review', approved_at = NULL"))

    # A pending request is erased and marked; its status stays.
    with eng.begin() as conn:
        conn.execute(text(_mark("duplicate")))
        row = conn.execute(
            text("SELECT status, number, tower_code, trial_price, phone FROM requests")
        ).one()
    assert row == ("pending_review", 1001, "MIG01", 1, None)

    # A rejected «سبب آخر» request keeps the reason's name and loses the note.
    with eng.begin() as conn:
        conn.execute(text(_INSERT_REQUEST), {"number": 1002})
        conn.execute(
            text(
                "UPDATE requests SET status = 'rejected', rejected_at = now(), "
                "rejected_by = (SELECT id FROM users WHERE role = 'super_admin'), "
                "rejection_reason = 'other', rejection_note = 'نص المراجع' WHERE number = 1002"
            )
        )
    _refused(eng, _mark(keep=("rejection_note",)) + " WHERE number = 1002")
    with eng.begin() as conn:
        conn.execute(text(_mark("other") + " WHERE number = 1002"))

    # A live «سبب آخر» rejection still needs its note.
    with eng.begin() as conn:
        conn.execute(text(_INSERT_REQUEST), {"number": 1003})
    _refused(
        eng,
        "UPDATE requests SET status = 'rejected', rejected_at = now(), "
        "rejected_by = (SELECT id FROM users WHERE role = 'super_admin'), "
        "rejection_reason = 'other' WHERE number = 1003",
    )

    # The new permission.
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (name, phone, password_hash, role, permissions) VALUES "
                "('أدمن الحذف', '07700000992', 'x', 'admin', '[\"review\", \"delete\"]')"
            )
        )
    _refused(
        eng,
        "INSERT INTO users (name, phone, password_hash, role, permissions) VALUES "
        "('أدمن مجهول', '07700000993', 'x', 'admin', '[\"erase\"]')",
    )

    # Erased data cannot be made NOT NULL again: the downgrade is refused.
    with pytest.raises(RuntimeError, match="0014 downgrade refused"):
        command.downgrade(cfg, "0013")

    # Without deleted rows or the new permission (this scratch database only), it round-trips.
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM requests WHERE deleted_at IS NOT NULL"))
        conn.execute(text("DELETE FROM users WHERE permissions @> '[\"delete\"]'"))
    command.downgrade(cfg, "0013")
    assert "deleted_at" not in _columns(eng, "requests")
    assert _columns(eng, "requests")["phone"]["nullable"] is False
    command.upgrade(cfg, "head")
