"""Backup test helpers (specs/016): a throwaway age key per test, synthetic files only.

`backup_env` gives a committed scratch database (pg_dump runs in another process and cannot see
the rolled-back test transaction), a temporary uploads folder, a temporary backup folder and a
throwaway key. `tests/integration/conftest.py` registers the fixtures.
"""

import itertools
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.backup.store import BackupStore
from app.core.timeutil import utc_now
from app.models import LegacyImage, User


@dataclass(frozen=True)
class AgeKey:
    identity: Path  # plaintext identity: only ever in tmp_path (tests) or tmpfs (operator)
    recipient: str


def make_age_key(directory: Path, name: str = "identity.txt") -> AgeKey:
    """A fresh X25519 key, written under `directory` (a pytest tmp_path). Never committed."""
    identity = directory / name
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    recipient = subprocess.run(
        ["age-keygen", "-y", str(identity)], check=True, capture_output=True, text=True
    ).stdout.strip()
    return AgeKey(identity=identity, recipient=recipient)


def image_name(n: int) -> str:
    """A stored-image file name in the image_store format (`<32 hex>.jpg`)."""
    return f"{n:032x}.jpg"


def new_image_name() -> str:
    return f"{uuid.uuid4().hex}.jpg"


# --- Committed scratch database -----------------------------------------------------------

_db_counter = itertools.count(1)


@pytest.fixture(scope="session")
def backup_template(engine) -> str:
    """A database migrated to head once per session; each test copies it (fast)."""
    from tests.conftest import API_ROOT

    url = engine.url.set(database=f"{engine.url.database}_bktpl")
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    admin.dispose()
    return url.database


@dataclass
class BackupEnv:
    url: str  # SQLAlchemy URL with password (passed to the backup code like DATABASE_URL)
    engine: Engine
    sessions: sessionmaker[Session]
    uploads: Path
    store: BackupStore
    key: AgeKey
    tmp: Path


@pytest.fixture
def backup_env(engine, backup_template, tmp_path):
    name = f"{engine.url.database}_bk{next(_db_counter)}"
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{name}" TEMPLATE "{backup_template}"'))
    url = engine.url.set(database=name)
    eng = create_engine(url, hide_parameters=True)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    store = BackupStore(tmp_path / "backups")
    store.ensure_layout()
    env = BackupEnv(
        url=url.render_as_string(hide_password=False),
        engine=eng,
        sessions=sessionmaker(bind=eng, expire_on_commit=False),
        uploads=uploads,
        store=store,
        key=make_age_key(tmp_path),
        tmp=tmp_path,
    )
    try:
        yield env
    finally:
        eng.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


# --- Synthetic data -----------------------------------------------------------------------


@dataclass(frozen=True)
class Seeded:
    requests: int
    legacy_subscribers: int
    sas_subscribers: int
    users: int
    image_names: frozenset[str]
    request_image_names: frozenset[str]


def _user(s: Session, role: str, phone: str) -> User:
    user = User(name=f"مستخدم نسخ {phone[-3:]}", phone=phone, password_hash="x", role=role)
    user.permissions = []
    s.add(user)
    s.flush()
    return user


def seed(env: BackupEnv, requests: int = 2) -> Seeded:
    """Committed synthetic data: requests with 2 images each, one legacy subscriber with 2 images,
    one SAS subscriber, an admin and a marketer."""
    from tests.helpers.card_images import scenario_jpeg
    from tests.helpers.legacy import legacy_subscriber
    from tests.helpers.requests import add_images, request_factory
    from tests.helpers.sas import sas_subscriber

    names: set[str] = set()
    with env.sessions() as s:
        admin = _user(s, "super_admin", "07710009001")
        marketer = _user(s, "marketer", "07710009002")
        for _ in range(requests):
            request = request_factory(s, marketer)
            names |= {image.file_name for image in add_images(s, request, env.uploads)}
        request_names = frozenset(names)
        legacy = legacy_subscriber(s, admin, family_number="LEGACY000000000001")
        for side in ("front", "back"):
            name = new_image_name()
            (env.uploads / name).write_bytes(scenario_jpeg("clear_front", 90, 60))
            s.add(
                LegacyImage(
                    legacy_subscriber_id=legacy.id,
                    side=side,
                    file_name=name,
                    size_bytes=100,
                    width=90,
                    height=60,
                    created_at=utc_now(),
                )
            )
            names.add(name)
        sas_subscriber(s, admin, username="ZZT01-07700000123")
        s.commit()
    return Seeded(
        requests=requests,
        legacy_subscribers=1,
        sas_subscribers=1,
        users=2,  # approved factory requests add no user
        image_names=frozenset(names),
        request_image_names=request_names,
    )
