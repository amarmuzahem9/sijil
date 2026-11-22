"""Test fixtures: real PostgreSQL test DB, one rolled-back transaction per test, synthetic users."""

import itertools
import os
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Must be set before the app (and its cached settings) are imported.
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if not _TEST_DB_URL:
    raise RuntimeError("TEST_DATABASE_URL is required to run the tests")
os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 32
os.environ["COOKIE_SECURE"] = "true"
# Tests never call the real card reader (specs/006 research.md R10).
os.environ["OCR_MODE"] = "fake"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core import timeutil  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402

API_ROOT = Path(__file__).resolve().parent.parent
TEST_PASSWORD = "Test-Passw0rd"


@pytest.fixture(scope="session")
def engine():
    url = make_url(_TEST_DB_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")

    eng = create_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:
    connection = engine.connect()
    outer = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _reset_login_limiter() -> Iterator[None]:
    from app.core.ratelimit import login_failures

    login_failures.reset()
    yield
    login_failures.reset()


@pytest.fixture
def client(db) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides.clear()


class FrozenClock:
    def set(self, value: datetime) -> None:
        timeutil._set_clock_for_tests(value)

    def advance(self, delta: timedelta) -> None:
        timeutil._set_clock_for_tests(timeutil.utc_now() + delta)


@pytest.fixture
def frozen_clock() -> Iterator[FrozenClock]:
    clock = FrozenClock()
    clock.set(timeutil.utc_now())
    yield clock
    timeutil._set_clock_for_tests(None)


_phone_counter = itertools.count(1)


@pytest.fixture
def make_user(db):
    """Create a synthetic user. Phones are 0771000xxxx; names are obviously fake."""

    def factory(
        role: str = "marketer",
        *,
        password: str = TEST_PASSWORD,
        must_change_password: bool = False,
        is_active: bool = True,
        phone: str | None = None,
        name: str | None = None,
    ) -> User:
        n = next(_phone_counter)
        user = User(
            name=name or f"مستخدم اختبار {n}",
            phone=phone or f"0771000{n:04d}",
            password_hash=hash_password(password),
            role=role,
            permissions=[],
            must_change_password=must_change_password,
            is_active=is_active,
        )
        db.add(user)
        db.flush()
        return user

    return factory


def login(client: TestClient, phone: str, password: str = TEST_PASSWORD):
    return client.post("/api/auth/login", json={"phone": phone, "password": password})


def auth_header(response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
