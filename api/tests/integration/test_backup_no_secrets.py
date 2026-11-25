"""No secret and no personal data outside the encryption (specs/016 FR-002, FR-011, T022)."""

import logging
import subprocess

from sqlalchemy.engine import make_url

from app.backup import crypto
from app.backup.serve import BackupService
from app.backup.store import DUMP
from tests.helpers.backup import seed

MARKERS = {
    "JWT_SECRET": "MARKER-JWT-5d1c" + "x" * 32,
    "OTPIQ_API_KEY": "MARKER-OTPIQ-a07e",
    "GOOGLE_MAPS_API_KEY": "MARKER-MAPS-91f3",
    "SUPERADMIN_PASSWORD": "MARKER-ADMIN-2b6d",
    "DEMO_MARKETER_PASSWORD": "MARKER-DEMO-e4a8",
}
# Personal values the synthetic requests carry (tests/helpers/requests.py).
PERSONAL = ("تجربة اختبار", "حي تجريبي", "0790000")


def _service(env) -> BackupService:
    return BackupService(
        sessions=env.sessions,
        store=env.store,
        uploads=env.uploads,
        recipient=env.key.recipient,
        database_url=env.url,
        nightly_minutes=0,
        min_free_bytes=1,
        external_dir="",
        app_commit="testcommit",
    )


def test_no_secret_anywhere_in_the_backup(backup_env, monkeypatch, caplog) -> None:
    env = backup_env
    for name, value in MARKERS.items():
        monkeypatch.setenv(name, value)
    db_password = make_url(env.url).password
    seed(env)
    caplog.set_level(logging.DEBUG)

    run = _service(env).run("manual")

    # Decrypt the dump to SQL text, and every image object.
    dump = env.tmp / "db.dump"
    crypto.decrypt_file(env.store.snapshot_dir(run.snapshot_id) / DUMP, dump, env.key.identity)
    sql = subprocess.run(
        ["pg_restore", "--file=-", str(dump)], capture_output=True, text=True, check=True
    ).stdout
    texts = {"dump.sql": sql}
    for path in env.store.root.rglob("*"):
        if path.is_file() and not path.name.endswith(".age"):
            texts[str(path)] = path.read_text(encoding="utf-8", errors="replace")
    for path in env.store.images.glob("*.age"):
        out = env.tmp / "img"
        crypto.decrypt_file(path, out, env.key.identity)
        texts[str(path)] = out.read_bytes().decode("latin-1")
    for where, content in texts.items():
        for value in [*MARKERS.values(), db_password]:
            assert value not in content, (where, value[:12])
    assert "users" in sql and "sas_subscribers" in sql  # it is a real dump

    # The plaintext files and the logs carry no personal data and no secret.
    plain = [c for w, c in texts.items() if w != "dump.sql" and not w.endswith(".age")]
    logs = caplog.text
    for content in [*plain, logs]:
        for value in [*PERSONAL, *MARKERS.values(), db_password]:
            assert value not in content, value[:12]
