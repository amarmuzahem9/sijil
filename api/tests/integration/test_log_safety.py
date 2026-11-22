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


def test_temporary_passwords_never_logged(client, make_user, caplog, capsys) -> None:
    """Feature 002: temporary passwords typed by admins never reach the logs."""
    caplog.set_level(logging.DEBUG)
    h = auth_header(login(client, make_user("super_admin").phone))
    temp_create, temp_reset = "Log-Temp-Create-1", "Log-Temp-Reset-2"
    created = client.post(
        "/api/admin/marketers",
        headers=h,
        json={"name": "مسوّق السجل", "phone": "07705550123", "temporary_password": temp_create},
    ).json()
    client.post(
        f"/api/admin/marketers/{created['id']}/reset-password",
        headers=h,
        json={"temporary_password": temp_reset},
    )
    client.post(  # rejected body: the validation error must not echo the value either
        "/api/admin/marketers",
        headers=h,
        json={"name": "س", "phone": "07705550124", "temporary_password": "Log-Bad-3"},
    )

    printed = capsys.readouterr()
    everything = (
        "\n".join(r.getMessage() for r in caplog.records)
        + _formatted(list(caplog.records))
        + printed.out
        + printed.err
    )
    for secret in (temp_create, temp_reset, "Log-Bad-3"):
        assert secret not in everything
    assert "Log-Temp" not in redact('{"temporary_password": "Log-Temp-9"}')


def test_redaction_filter() -> None:
    assert "s3cr3t" not in redact('password="s3cr3t" user=1')
    assert "abc.def.ghi" not in redact("Authorization: Bearer abc.def.ghi")
    assert "tok123" not in redact("cookie: sijil_refresh=tok123")
    assert "tok456" not in redact('{"refresh_token": "tok456"}')
    assert redact("phone=07700000001") == "phone=07700000001"


def test_no_card_data_in_logs(client, db, make_user, caplog, capsys, tmp_path, monkeypatch) -> None:
    """specs/005 FR-022: failed draft saves and uploads never log card data or file names."""
    import io
    import uuid

    from PIL import Image
    from sqlalchemy import select

    from app.models import DraftImage

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    caplog.set_level(logging.DEBUG)
    headers = auth_header(login(client, make_user("marketer").phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    national_id, family, phone, name = "199087654321", "ZX9Y8W", "07809876543", "اسم سري للاختبار"

    draft_id = str(uuid.uuid4())
    client.put(
        f"/api/drafts/{draft_id}",
        json={
            "changes": {
                "first_name": name,
                "national_id": national_id,
                "family_number": family,
                "phone_input": phone,
            }
        },
        headers=headers,
    )
    # Failures: stale version, over-length value, unknown field, broken image, bad image id.
    client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 99, "changes": {"national_id": national_id}},
        headers=headers,
    )
    client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 1, "changes": {"landmark": national_id * 20}},
        headers=headers,
    )
    client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": 1, "changes": {"secret": family}},
        headers=headers,
    )
    client.post(
        f"/api/drafts/{draft_id}/images/front",
        files={"file": (f"{national_id}.jpg", b"\xff\xd8\xff broken", "image/jpeg")},
        headers=headers,
    )
    buf = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buf, format="JPEG")
    client.post(
        f"/api/drafts/{draft_id}/images/back",
        files={"file": (f"{family}.jpg", buf.getvalue(), "image/jpeg")},
        headers=headers,
    )
    stored = db.scalars(select(DraftImage.file_name)).one()
    (tmp_path / stored).unlink()  # the file vanished: the open fails and logs
    image_id = db.scalars(select(DraftImage.id)).one()
    client.get(f"/api/draft-images/{image_id}", headers=headers)
    client.delete(f"/api/drafts/{draft_id}", headers=headers)

    raw = "\n".join(r.getMessage() for r in caplog.records)
    printed = capsys.readouterr()
    everything = raw + _formatted(list(caplog.records)) + printed.out + printed.err
    for secret in (national_id, family, phone, name, stored):
        assert secret not in everything
