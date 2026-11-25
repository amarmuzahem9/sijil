"""Restore: verify, stage, database (specs/016 US2, FR-012–FR-014, research R7, T031)."""

import itertools
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text

from app.backup import crypto, restore
from app.backup.manifest import Manifest
from app.backup.restore import RestoreRefused
from app.backup.snapshot import SnapshotConfig, take_snapshot
from app.backup.store import DUMP, MANIFEST
from app.models import Request
from tests.helpers.backup import make_age_key, seed
from tests.helpers.requests import request_factory

_n = itertools.count(1)


def _snap(env) -> Manifest:
    seed(env)
    return take_snapshot(
        SnapshotConfig(
            store=env.store,
            uploads=env.uploads,
            recipient=env.key.recipient,
            database_url=env.url,
            app_commit="testcommit",
        ),
        "nightly",
    )


def _flip_last_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))


@pytest.fixture
def empty_db(engine):
    name = f"{engine.url.database}_rs{next(_n)}"
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = engine.url.set(database=name).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


# --- verify (no passphrase needed) ----------------------------------------------------------


def test_verify_accepts_a_good_snapshot(backup_env) -> None:
    manifest = _snap(backup_env)
    assert restore.verify(backup_env.store, manifest.id) == manifest


def test_verify_refuses_a_damaged_image_object(backup_env) -> None:
    manifest = _snap(backup_env)
    _flip_last_byte(backup_env.store.image_path(manifest.images[0].name))
    with pytest.raises(RestoreRefused) as info:
        restore.verify(backup_env.store, manifest.id)
    assert info.value.code == "damaged"


def test_verify_refuses_a_damaged_dump(backup_env) -> None:
    manifest = _snap(backup_env)
    _flip_last_byte(backup_env.store.snapshot_dir(manifest.id) / DUMP)
    with pytest.raises(RestoreRefused) as info:
        restore.verify(backup_env.store, manifest.id)
    assert info.value.code == "damaged"


def test_verify_refuses_a_missing_object(backup_env) -> None:
    manifest = _snap(backup_env)
    backup_env.store.image_path(manifest.images[0].name).unlink()
    with pytest.raises(RestoreRefused) as info:
        restore.verify(backup_env.store, manifest.id)
    assert info.value.code == "damaged"


def test_verify_refuses_an_incomplete_snapshot(backup_env) -> None:
    manifest = _snap(backup_env)
    (backup_env.store.snapshot_dir(manifest.id) / "DONE").unlink()
    with pytest.raises(RestoreRefused) as info:
        restore.verify(backup_env.store, manifest.id)
    assert info.value.code == "incomplete"


def test_verify_refuses_an_unknown_snapshot(backup_env) -> None:
    with pytest.raises(RestoreRefused) as info:
        restore.verify(backup_env.store, "20200101-000000-nightly")
    assert info.value.code == "not_found"


# --- revision ---------------------------------------------------------------------------


def test_revision_from_this_code_or_older_is_accepted(backup_env) -> None:
    manifest = _snap(backup_env)
    restore.check_revision(manifest)  # head
    restore.check_revision(manifest.__class__(**{**manifest.__dict__, "alembic_revision": "0018"}))


def test_revision_newer_than_the_code_is_refused(backup_env) -> None:
    manifest = _snap(backup_env)
    newer = manifest.__class__(**{**manifest.__dict__, "alembic_revision": "9999"})
    with pytest.raises(RestoreRefused) as info:
        restore.check_revision(newer)
    assert info.value.code == "revision_unknown"


# --- stage images -----------------------------------------------------------------------


def test_stage_images_decrypts_every_image_and_checks_it(backup_env) -> None:
    env = backup_env
    manifest = _snap(env)
    staged = env.tmp / "staged"
    staged.mkdir()
    assert restore.stage_images(env.store, manifest, env.key.identity, staged) == len(
        manifest.images
    )
    for entry in manifest.images:
        assert crypto.sha256_file(staged / entry.name) == entry.sha256_plain
        assert (staged / entry.name).read_bytes() == (env.uploads / entry.name).read_bytes()


def test_stage_images_with_a_wrong_key_fails(backup_env) -> None:
    env = backup_env
    manifest = _snap(env)
    other = make_age_key(env.tmp, "other.txt")
    staged = env.tmp / "staged"
    staged.mkdir()
    with pytest.raises(RestoreRefused) as info:
        restore.stage_images(env.store, manifest, other.identity, staged)
    assert info.value.code == "decrypt_failed"


# --- database ---------------------------------------------------------------------------


def test_restore_database_into_an_empty_database(backup_env, empty_db) -> None:
    env = backup_env
    manifest = _snap(env)
    restore.restore_database(env.store, manifest, env.key.identity, empty_db)
    assert restore.database_counts(empty_db) == manifest.counts


def test_restore_database_replaces_later_changes(backup_env) -> None:
    env = backup_env
    manifest = _snap(env)
    with env.sessions() as s:
        marketer = s.scalar(select(Request.marketer_id).limit(1))
        from app.models import User

        request_factory(s, s.get(User, marketer))
        s.commit()
        assert s.scalar(select(func.count()).select_from(Request)) == manifest.counts.requests + 1
    env.engine.dispose()
    restore.restore_database(env.store, manifest, env.key.identity, env.url)
    assert restore.database_counts(env.url) == manifest.counts


def test_restore_database_writes_no_plaintext_dump(backup_env, empty_db, tmp_path) -> None:
    env = backup_env
    manifest = _snap(env)
    before = {p for p in tmp_path.rglob("*")}
    restore.restore_database(env.store, manifest, env.key.identity, empty_db)
    new = {p for p in tmp_path.rglob("*")} - before
    assert not [p for p in new if p.is_file()]


def test_manifest_file_is_what_verify_reads(backup_env) -> None:
    manifest = _snap(backup_env)
    text_ = (backup_env.store.snapshot_dir(manifest.id) / MANIFEST).read_text()
    assert Manifest.from_json(text_) == restore.verify(backup_env.store, manifest.id)
