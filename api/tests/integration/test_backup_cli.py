"""`python -m app.backup` commands (specs/016 contracts/cli.md, T026). Exit codes: 0 ok,
3 busy, 4 disk_low, 1 other failure."""

import pytest
from sqlalchemy import create_engine, text

from app.backup import __main__ as cli
from app.backup.serve import BACKUP_LOCK, BackupService
from tests.helpers.backup import seed


@pytest.fixture
def service(backup_env, monkeypatch):
    env = backup_env

    def build(**over) -> BackupService:
        args = {
            "sessions": env.sessions,
            "store": env.store,
            "uploads": env.uploads,
            "recipient": env.key.recipient,
            "database_url": env.url,
            "nightly_minutes": 180,
            "min_free_bytes": 1,
            "external_dir": "",
            "app_commit": "testcommit",
        }
        svc = BackupService(**(args | over))
        monkeypatch.setattr(BackupService, "from_settings", classmethod(lambda cls: svc))
        return svc

    return build


def test_now_then_list(backup_env, service, capsys) -> None:
    seed(backup_env)
    service()
    assert cli.main(["now", "--kind", "pre_deploy"]) == 0
    out = capsys.readouterr().out
    (sid,) = backup_env.store.list_snapshots()
    assert sid.endswith("-pre_deploy") and sid in out
    assert cli.main(["list"]) == 0
    listing = capsys.readouterr().out
    assert sid in listing and "pre_deploy" in listing


def test_now_busy_exits_3(backup_env, service) -> None:
    service()
    other = create_engine(backup_env.url)
    with other.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": BACKUP_LOCK})
        assert cli.main(["now"]) == 3
        conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": BACKUP_LOCK})
    other.dispose()


def test_now_disk_low_exits_4(backup_env, service) -> None:
    service(min_free_bytes=10**18)
    assert cli.main(["now"]) == 4


def test_now_without_key_exits_1(backup_env, service, capsys) -> None:
    service(recipient="")
    assert cli.main(["now"]) == 1
    assert "no_key" in capsys.readouterr().err


def test_unknown_kind_refused(service) -> None:
    service()
    with pytest.raises(SystemExit):
        cli.main(["now", "--kind", "nightly"])  # nightly belongs to the schedule
