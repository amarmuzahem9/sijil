"""Principle II: no password, token or cookie value may reach the logs."""

import logging

from app.cli import bootstrap
from app.config import get_settings
from app.logging_config import JsonFormatter, RedactFilter, redact
from tests.conftest import TEST_PASSWORD, auth_header, login

NEW_PASSWORD = "Log-Safety-Passw0rd"
BOOT_PASSWORD = "Boot-Log-Passw0rd"


def _formatted(records: list[logging.LogRecord]) -> str:
    """Render records exactly as production does (filter + JSON formatter)."""
    fmt, flt = JsonFormatter(), RedactFilter()
    out = []
    for record in records:
        flt.filter(record)
        out.append(fmt.format(record))
    return "\n".join(out)


def test_no_secrets_in_logs(client, db, make_user, caplog, capsys) -> None:
    caplog.set_level(logging.DEBUG)
    user = make_user(must_change_password=True)

    login(client, user.phone, "Wrong-Passw0rd-123")
    ok = login(client, user.phone)
    access = ok.json()["access_token"]
    refresh_cookie = ok.cookies["sijil_refresh"]
    changed = client.post(
        "/api/auth/change-password",
        headers=auth_header(ok),
        json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD},
    )
    new_cookie = changed.cookies["sijil_refresh"]
    client.post("/api/auth/refresh")
    bootstrap(
        db,
        get_settings().model_copy(
            update={
                "superadmin_phone": "07705550099",
                "superadmin_name": "أدمن",
                "superadmin_password": BOOT_PASSWORD,
            }
        ),
    )

    raw = "\n".join(r.getMessage() for r in caplog.records)
    printed = capsys.readouterr()
    everything = raw + _formatted(list(caplog.records)) + printed.out + printed.err
    for secret in (
        TEST_PASSWORD,
        NEW_PASSWORD,
        BOOT_PASSWORD,
        "Wrong-Passw0rd-123",
        access,
        refresh_cookie,
        new_cookie,
    ):
        assert secret not in everything


def test_redaction_filter() -> None:
    assert "s3cr3t" not in redact('password="s3cr3t" user=1')
    assert "abc.def.ghi" not in redact("Authorization: Bearer abc.def.ghi")
    assert "tok123" not in redact("cookie: sijil_refresh=tok123")
    assert "tok456" not in redact('{"refresh_token": "tok456"}')
    assert redact("phone=07700000001") == "phone=07700000001"
