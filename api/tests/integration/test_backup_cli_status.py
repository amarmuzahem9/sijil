"""`python -m app.backup status` for the operator (specs/016 contracts/cli.md; moved from T037 to
batch 4 with the warnings it prints)."""

from datetime import timedelta

import pytest

from app.backup import __main__ as cli
from app.core.timeutil import utc_now
from app.models import BackupEvent, BackupRun, BackupStatus


@pytest.fixture
def settings_on(backup_env, monkeypatch):
    from app import db as app_db
    from app.config import get_settings

    def clear() -> None:
        if app_db.get_engine.cache_info().currsize:
            app_db.get_engine().dispose()
        app_db.get_sessionmaker.cache_clear()
        app_db.get_engine.cache_clear()
        get_settings.cache_clear()

    monkeypatch.setenv("DATABASE_URL", backup_env.url)
    monkeypatch.setenv("BACKUP_DIR", str(backup_env.store.root))
    clear()
    yield backup_env
    clear()


def test_status_prints_the_last_records_and_the_warnings(settings_on, capsys) -> None:
    env = settings_on
    now = utc_now()
    with env.sessions() as s:
        s.add(BackupStatus(id=1, heartbeat_at=now, nightly_at="03:00", key_configured=True))
        s.add(
            BackupRun(
                id="20261127-000000-nightly",
                snapshot_id="20261127-000000-nightly",
                kind="nightly",
                status="succeeded",
                started_at=now - timedelta(hours=1),
                finished_at=now - timedelta(hours=1),
                total_size=1234,
            )
        )
        s.add(BackupEvent(id="d.json", type="drill", at=now, result="passed"))
        s.commit()
    assert cli.main(["status"]) == 1  # a warning: no external copy yet
    out = capsys.readouterr().out
    assert "آخر نسخة" in out and "20261127-000000-nightly" in out
    assert "تجربة الاسترجاع" in out and "نجحت" in out
    assert "النسخة الأسبوعية على الهارد الخارجي متأخرة" in out  # no external copy yet


def test_status_exit_code_says_whether_something_is_wrong(settings_on) -> None:
    env = settings_on
    with env.sessions() as s:
        s.add(BackupStatus(id=1, heartbeat_at=utc_now(), nightly_at="03:00", key_configured=False))
        s.commit()
    assert cli.main(["status"]) == 1
