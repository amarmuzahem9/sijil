"""One snapshot of the database and every stored image (specs/016 US1, research R3/R4, T015)."""

import subprocess

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.backup import crypto
from app.backup.manifest import Manifest
from app.backup.snapshot import SnapshotConfig, take_snapshot
from app.backup.store import DUMP, MANIFEST
from tests.conftest import API_ROOT
from tests.helpers.backup import new_image_name, seed


def _head() -> str:
    """The newest migration, so a new feature's migration does not break this test."""
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _cfg(env) -> SnapshotConfig:
    return SnapshotConfig(
        store=env.store,
        uploads=env.uploads,
        recipient=env.key.recipient,
        database_url=env.url,
        app_commit="testcommit",
    )


def test_snapshot_holds_database_and_every_image(backup_env) -> None:
    env = backup_env
    seeded = seed(env)
    orphan = new_image_name()  # a file no row refers to is still part of the storage (FR-001)
    (env.uploads / orphan).write_bytes(b"\xff\xd8\xff orphan")
    (env.uploads / "upload.jpg.part").write_bytes(b"half")  # an upload in progress is skipped

    manifest = take_snapshot(_cfg(env), "nightly")

    folder = env.store.snapshot_dir(manifest.id)
    assert {p.name for p in folder.iterdir()} == {DUMP, MANIFEST, "DONE"}
    assert Manifest.from_json((folder / MANIFEST).read_text()) == manifest
    assert manifest.kind == "nightly" and manifest.id.endswith("-nightly")
    assert manifest.app_commit == "testcommit"
    assert manifest.alembic_revision == _head()
    assert manifest.missing_referenced == 0
    counts = manifest.counts
    assert (counts.requests, counts.legacy_subscribers, counts.sas_subscribers, counts.users) == (
        seeded.requests,
        seeded.legacy_subscribers,
        seeded.sas_subscribers,
        seeded.users,
    )
    assert counts.drafts == 0
    assert counts.audit_entries >= 0
    # Every file in storage, legacy images included.
    assert manifest.image_names == set(seeded.image_names) | {orphan}
    assert manifest.dump.sha256_enc == crypto.sha256_file(folder / DUMP)
    assert manifest.total_size == manifest.dump.size + sum(
        env.store.image_path(n).stat().st_size for n in manifest.image_names
    )


def test_dump_decrypts_and_lists(backup_env) -> None:
    env = backup_env
    seed(env)
    manifest = take_snapshot(_cfg(env), "manual")
    plain = env.tmp / "db.dump"
    crypto.decrypt_file(env.store.snapshot_dir(manifest.id) / DUMP, plain, env.key.identity)
    listing = subprocess.run(
        ["pg_restore", "--list", str(plain)], capture_output=True, text=True, check=True
    ).stdout
    for table in ("requests", "request_images", "legacy_images", "sas_subscribers", "audit_log"):
        assert f"TABLE DATA public {table}" in listing, table


def test_every_object_decrypts_to_its_hash(backup_env) -> None:
    env = backup_env
    seed(env)
    manifest = take_snapshot(_cfg(env), "nightly")
    for entry in manifest.images:
        out = env.tmp / ("plain-" + entry.name)
        crypto.decrypt_file(env.store.image_path(entry.name), out, env.key.identity)
        assert crypto.sha256_file(out) == entry.sha256_plain
        assert out.read_bytes() == (env.uploads / entry.name).read_bytes()
        assert crypto.sha256_file(env.store.image_path(entry.name)) == entry.sha256_enc


def test_second_snapshot_writes_no_object_again(backup_env, frozen_clock) -> None:
    from datetime import timedelta

    env = backup_env
    seed(env)
    first = take_snapshot(_cfg(env), "nightly")
    mtimes = {n: env.store.image_path(n).stat().st_mtime_ns for n in first.image_names}
    frozen_clock.advance(timedelta(days=1))
    second = take_snapshot(_cfg(env), "nightly")
    assert second.id != first.id
    assert second.image_names == first.image_names
    assert {n: env.store.image_path(n).stat().st_mtime_ns for n in second.image_names} == mtimes
    # Only the dump is new in the second snapshot.
    assert second.total_size == second.dump.size


def test_snapshot_times_are_utc(backup_env) -> None:
    env = backup_env
    manifest = take_snapshot(_cfg(env), "pre_deploy", requested_by=None)
    assert manifest.started_at.utcoffset().total_seconds() == 0
    assert manifest.finished_at >= manifest.started_at
