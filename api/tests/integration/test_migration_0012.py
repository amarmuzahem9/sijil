"""Migration 0012_request_tower_name (system.md v1.12 §5): drafts and requests keep the tower name.
Requests submitted before it get the tower's current name."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.conftest import API_ROOT


def test_columns_exist(engine) -> None:
    insp = inspect(engine)
    req = {c["name"]: c for c in insp.get_columns("requests")}
    assert req["tower_name"]["nullable"] is False
    assert "tower_name" in {c["name"] for c in insp.get_columns("drafts")}


def test_backfill_downgrade_and_upgrade_again(engine) -> None:
    url = engine.url.set(database=f"{engine.url.database}_mig12")
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    try:
        cfg = Config(str(API_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
        cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
        cfg.attributes["configure_logger"] = False
        command.upgrade(cfg, "0011")
        eng = create_engine(url)
        try:
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
                conn.execute(
                    text("INSERT INTO plans (name, trial_price, second_price) VALUES ('P', 1, 2)")
                )
                conn.execute(
                    text(
                        "INSERT INTO requests (number, draft_id, marketer_id, type, status, "
                        "first_name, father_name, grandfather_name, great_grandfather_name, "
                        "surname, mother_first_name, mother_second_name, full_name, no_surname, "
                        "national_id, national_id_input, family_number, family_key, birth_date, "
                        "issue_date, expiry_date, birth_place, issuing_authority, card_fields, "
                        "card_readings, location_lat, location_lng, location_source, address, "
                        "landmark, area_id, tower_id, plan_id, area_name, tower_code, plan_name, "
                        "trial_price, second_price, phone, username, otp_verified_at, "
                        "submitted_at) "
                        "SELECT 1001, gen_random_uuid(), u.id, 'new', 'pending_review', "
                        "'ا','ب','ج','د','ه','و','ز','ا ب ج د ه', false, '199000000001', "
                        "'199000000001', '1A', '1A', '1990-01-01', '2020-01-01', '2030-01-01', "
                        "'بغداد', 'جهة', '{}', '{}', 33.3, 44.3, 'gps', 'عنوان', 'نقطة', "
                        "a.id, t.id, p.id, 'منطقة', 'MIG01', 'P', 1, 2, '07800000990', "
                        "'MIG01-07800000990', now(), now() "
                        "FROM users u, areas a, towers t, plans p"
                    )
                )
        finally:
            eng.dispose()
        command.upgrade(cfg, "head")
        eng = create_engine(url)
        try:
            with eng.connect() as conn:
                assert conn.execute(text("SELECT tower_name FROM requests")).scalar_one() == (
                    "برج الترحيل"
                )
        finally:
            eng.dispose()
        command.downgrade(cfg, "0011")
        command.upgrade(cfg, "head")
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        admin.dispose()
