"""Migration 0020_commissions (specs/017 data-model.md).

commission_payments: one «تم الدفع» per marketer and Baghdad month, its figures checked.
commission_payment_requests: the requests of a payment; a request is in at most one payment.
"""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.conftest import API_ROOT
from tests.helpers.requests import request_factory

_TABLES = ("commission_payments", "commission_payment_requests")


def test_tables_and_columns(engine) -> None:
    insp = inspect(engine)
    assert set(_TABLES) <= set(insp.get_table_names())
    pay = {c["name"]: c for c in insp.get_columns("commission_payments")}
    assert {
        "id",
        "marketer_id",
        "month",
        "count",
        "tier_min_count",
        "rate",
        "amount",
        "paid_by",
        "paid_at",
    } == set(pay)
    for column in pay.values():
        assert column["nullable"] is False, column["name"]
    req = {c["name"]: c for c in insp.get_columns("commission_payment_requests")}
    assert {"request_id", "payment_id"} == set(req)
    assert req["payment_id"]["nullable"] is False
    assert insp.get_pk_constraint("commission_payment_requests")["constrained_columns"] == [
        "request_id"
    ]


_PAY = (
    "INSERT INTO commission_payments "
    "(marketer_id, month, count, tier_min_count, rate, amount, paid_by, paid_at) "
    "VALUES (:m, :month, :count, :tmin, :rate, :amount, :m, now()) RETURNING id"
)


def _pay(conn, **over):
    params = {"month": "2026-10-01", "count": 30, "tmin": 30, "rate": 7000, "amount": 210000}
    params |= over
    return conn.execute(text(_PAY), params).scalar_one()


@pytest.mark.parametrize(
    "over",
    [
        {"month": "2026-10-02"},  # not the first day
        {"count": 0, "amount": 0},  # count > 0
        {"tmin": 31},  # tier lowest count above the count
        {"tmin": -1},
        {"rate": 0, "amount": 0},  # rate range
        {"rate": 10_000_001, "amount": 30 * 10_000_001},
        {"amount": 210001},  # amount = count × rate
    ],
    ids=lambda o: ",".join(o),
)
def test_payment_checks(db, make_user, over) -> None:
    marketer = make_user(role="marketer")
    conn = db
    with pytest.raises(IntegrityError), db.begin_nested():
        _pay(conn, m=marketer.id, **over)


def test_one_payment_per_marketer_and_month(db, make_user) -> None:
    marketer = make_user(role="marketer")
    conn = db
    _pay(conn, m=marketer.id)
    _pay(conn, m=marketer.id, month="2026-09-01")
    with pytest.raises(IntegrityError), db.begin_nested():
        _pay(conn, m=marketer.id)


def test_a_request_is_in_one_payment_only(db, make_user) -> None:
    marketer = make_user(role="marketer")
    request = request_factory(db, marketer, status="linked")
    conn = db
    first = _pay(conn, m=marketer.id, count=1, tmin=0, rate=5000, amount=5000)
    second = _pay(conn, m=marketer.id, month="2026-09-01", count=1, tmin=0, rate=5000, amount=5000)
    link = "INSERT INTO commission_payment_requests (request_id, payment_id) VALUES (:r, :p)"
    conn.execute(text(link), {"r": request.id, "p": first})
    with pytest.raises(IntegrityError), db.begin_nested():
        conn.execute(text(link), {"r": request.id, "p": second})
    with pytest.raises(IntegrityError), db.begin_nested():
        conn.execute(
            text("INSERT INTO commission_payment_requests (request_id) VALUES (:r)"),
            {"r": request_factory(db, marketer, status="linked").id},
        )


@pytest.fixture
def scratch_db(engine):
    """A fresh database at head."""
    url = engine.url.set(database=f"{engine.url.database}_mig20")
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
    assert set(_TABLES) <= set(inspect(eng).get_table_names())
    command.downgrade(cfg, "0019")
    assert not set(_TABLES) & set(inspect(eng).get_table_names())
    command.upgrade(cfg, "head")
    assert set(_TABLES) <= set(inspect(eng).get_table_names())
