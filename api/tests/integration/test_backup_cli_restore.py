"""The restore and drill commands the operator scripts call (specs/016 contracts/cli.md, T034,
T036–T038). Exit codes: 0 ok, 6 drill failed, 7 restore refused."""

import io
import json

import pytest
from sqlalchemy import create_engine, select, text

from app.backup import __main__ as cli
from app.backup import keyfile
from app.backup.snapshot import SnapshotConfig, take_snapshot
from app.models import AuditLog, BackupEvent
from tests.helpers.backup import seed

PASS = "synthetic-drill-passphrase"


@pytest.fixture
def setup(backup_env, monkeypatch, engine):
    """Settings pointing at the scratch database and folders; a key.age with a known passphrase."""
    env = backup_env
    env.store.key_path.unlink(missing_ok=True)
    recipient = keyfile.create(env.store.key_path, passphrase=PASS)
    monkeypatch.setenv("BACKUP_DIR", str(env.store.root))
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.setenv("BACKUP_AGE_RECIPIENT", recipient)
    from app import db as app_db
    from app.config import get_settings

    def clear_caches() -> None:
        # `record restore` opens the app's own cached engine: it must not outlive this test
        # (the scratch database is dropped afterwards).
        if app_db.get_engine.cache_info().currsize:
            app_db.get_engine().dispose()
        app_db.get_sessionmaker.cache_clear()
        app_db.get_engine.cache_clear()
        get_settings.cache_clear()

    clear_caches()
    seed(env)
    manifest = take_snapshot(
        SnapshotConfig(
            store=env.store,
            uploads=env.uploads,
            recipient=recipient,
            database_url=env.url,
            app_commit="testcommit",
        ),
        "nightly",
    )
    yield env, manifest
    clear_caches()


def _stdin(monkeypatch, value: str) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(value))


def test_latest_show_check_files(setup, capsys) -> None:
    env, manifest = setup
    assert cli.main(["latest"]) == 0
    assert capsys.readouterr().out.strip() == manifest.id
    assert cli.main(["show", manifest.id]) == 0
    shown = capsys.readouterr().out
    assert manifest.id in shown and "DATE=" in shown and "طلبات" in shown
    assert cli.main(["check", manifest.id]) == 0
    capsys.readouterr()
    assert cli.main(["files", manifest.id]) == 0
    files = capsys.readouterr().out.split()
    assert "key.age" in files
    assert f"snapshots/{manifest.id}/manifest.json" in files
    assert f"images/{manifest.images[0].name}.age" in files
    assert all(not f.startswith("/") and ".." not in f for f in files)


def test_check_refuses_a_damaged_snapshot(setup, capsys) -> None:
    env, manifest = setup
    obj = env.store.image_path(manifest.images[0].name)
    obj.write_bytes(obj.read_bytes()[:-1])
    assert cli.main(["check", manifest.id]) == 7
    assert "damaged" in capsys.readouterr().err


def test_restore_into_then_verify_restored(setup, monkeypatch, capsys) -> None:
    env, manifest = setup
    staging = env.tmp / "staging"
    staging.mkdir()
    target = env.tmp / "restored-uploads"
    target.mkdir()
    (target / "leftover.jpg.part").write_bytes(b"x")
    env.engine.dispose()
    _stdin(monkeypatch, PASS + "\n")
    code = cli.main(
        [
            "restore-into",
            manifest.id,
            "--staging",
            str(staging),
            "--uploads",
            str(target),
            "--passphrase-stdin",
        ]
    )
    assert code == 0, capsys.readouterr().err
    assert sorted(p.name for p in target.iterdir()) == sorted(manifest.image_names)
    capsys.readouterr()
    assert cli.main(["verify-restored", manifest.id, "--uploads", str(target)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["passed"] is True


def test_restore_into_with_a_wrong_passphrase_changes_nothing(setup, monkeypatch) -> None:
    env, manifest = setup
    staging = env.tmp / "staging"
    staging.mkdir()
    target = env.tmp / "restored-uploads"
    target.mkdir()
    (target / "keep.jpg").write_bytes(b"x")
    _stdin(monkeypatch, "wrong-passphrase-here\n")
    assert (
        cli.main(
            [
                "restore-into",
                manifest.id,
                "--staging",
                str(staging),
                "--uploads",
                str(target),
                "--passphrase-stdin",
            ]
        )
        == 7
    )
    assert [p.name for p in target.iterdir()] == ["keep.jpg"]


def test_verify_restored_failure_exits_6(setup, capsys) -> None:
    env, manifest = setup
    empty = env.tmp / "empty"
    empty.mkdir()
    assert cli.main(["verify-restored", manifest.id, "--uploads", str(empty)]) == 6
    assert json.loads(capsys.readouterr().out)["reason"] == "images_missing"


def test_record_drill_from_stdin(setup, monkeypatch) -> None:
    env, manifest = setup
    _stdin(monkeypatch, json.dumps({"passed": True, "reason": None, "compared": {"requests": 1}}))
    assert cli.main(["record", "drill", manifest.id, "--source-label", "server"]) == 0
    ((name, data),) = [h for h in env.store.read_history() if h[0].endswith("-drill.json")]
    assert data["result"] == "passed" and data["details"]["source"] == "server"


def test_record_restore_writes_history_and_audit(setup) -> None:
    env, manifest = setup
    assert (
        cli.main(["record", "restore", manifest.id, "--pre-restore", "20261125-000001-pre_restore"])
        == 0
    )
    ((name, data),) = [h for h in env.store.read_history() if h[0].endswith("-restore.json")]
    assert data["result"] == "succeeded" and data["snapshot_id"] == manifest.id
    assert data["details"] == {"pre_restore": "20261125-000001-pre_restore"}
    eng = create_engine(env.url)
    with eng.connect() as conn:
        row = conn.execute(
            text(
                "SELECT actor_id, entity_type, entity_id, after FROM audit_log "
                "WHERE action = 'backup.restore'"
            )
        ).one()
    eng.dispose()
    assert row.actor_id is None and row.entity_type == "backup_run"
    assert row.entity_id == manifest.id
    assert row.after == {"pre_restore": "20261125-000001-pre_restore"}
    with env.sessions() as s:
        assert s.scalar(select(AuditLog).where(AuditLog.action == "backup.restore")) is not None
        assert s.scalar(select(BackupEvent)) is None  # the mirror is the service's job


def test_record_deploy(setup) -> None:
    env, manifest = setup
    args = ["record", "deploy", manifest.id, "--mode", "production", "--old-commit", "aaa1111"]
    args += ["--new-commit", "bbb2222", "--result", "failed"]
    assert cli.main(args) == 0
    ((name, data),) = [h for h in env.store.read_history() if h[0].endswith("-deploy.json")]
    assert data == {
        "result": "failed",
        "snapshot_id": manifest.id,
        "details": {
            "mode": "production",
            "old_commit": "aaa1111",
            "new_commit": "bbb2222",
            "pre_deploy": manifest.id,
        },
    }


def test_record_deploy_on_a_first_install_has_no_snapshot(setup) -> None:
    env, _ = setup
    args = ["record", "deploy", "-", "--mode", "staging", "--old-commit", "-"]
    args += ["--new-commit", "ccc3333", "--result", "succeeded"]
    assert cli.main(args) == 0
    ((_, data),) = [h for h in env.store.read_history() if h[0].endswith("-deploy.json")]
    assert data["snapshot_id"] is None and data["details"]["pre_deploy"] is None
    assert data["details"]["old_commit"] is None
