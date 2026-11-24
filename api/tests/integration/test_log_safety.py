"""Principle II: no password, token or cookie value may reach the logs."""

import json
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


def test_card_readings_never_log_card_data(
    client, db, make_user, caplog, capsys, tmp_path, monkeypatch
):
    """specs/006 FR-019 / SC-007: a full reading, a re-shoot and a failure log no card text."""
    import uuid

    from app.services.card_reader_fake_data import AUTHORITY, DOC, FAMILY, NID, NID_OTHER
    from tests.helpers.card_images import scenario_jpeg

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    caplog.set_level(logging.DEBUG)
    user = make_user("marketer")
    headers = auth_header(login(client, user.phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    for front, back in (
        ("clear_front", "back_nid_mismatch"),
        ("two_cards", "reader_failure"),
        ("front_female_2000", "back_2000"),
    ):
        draft_id = str(uuid.uuid4())
        client.put(f"/api/drafts/{draft_id}", json={"changes": {}}, headers=headers)
        for side, scenario in (("front", front), ("back", back)):
            client.post(
                f"/api/drafts/{draft_id}/images/{side}",
                files={"file": ("x.jpg", scenario_jpeg(scenario), "image/jpeg")},
                headers=headers,
            )
        client.get(f"/api/drafts/{draft_id}/card-reading", headers=headers)
        client.post(f"/api/drafts/{draft_id}/card-reading/retry", headers=headers)

    raw = "\n".join(r.getMessage() for r in caplog.records)
    printed = capsys.readouterr()
    everything = raw + _formatted(list(caplog.records)) + printed.out + printed.err
    assert "card reading" in everything  # the readings did log their state
    for secret in (
        NID,
        NID_OTHER,
        "200512345678",
        DOC,
        FAMILY,
        AUTHORITY,
        "مشترك",
        "تجريبي",
        "اختبار",
        "الوهمي",
        "مشتركة",
        "مدينة",
        "1999-01-01",
        "1999/01/01",
        "2005-03-14",
        "990101",
        "050314",
    ):
        assert secret not in everything, secret


def test_otp_codes_never_leak(client, db, make_user, caplog, capsys) -> None:
    """specs/007 FR-016, FR-017, SC-004: the code appears only in the WhatsApp message (here the
    fake outbox): not in logs, not in any response body, not in the database in plain form. The
    full phone and the provider key are not logged either."""
    import uuid

    from sqlalchemy import select

    from app.models import OtpChallenge
    from app.services.otp_sender import get_otp_sender

    caplog.set_level(logging.DEBUG)
    fake = get_otp_sender()
    fake.outbox.clear()
    headers = auth_header(login(client, make_user("marketer").phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    phone = "07809871234"
    draft_id = str(uuid.uuid4())
    bodies = [
        client.put(
            f"/api/drafts/{draft_id}", json={"changes": {"phone_input": phone}}, headers=headers
        ).text
    ]

    bodies.append(client.post(f"/api/drafts/{draft_id}/otp/send", headers=headers).text)
    code = fake.outbox[-1][1]
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for entry in (wrong, "12", code):
        bodies.append(
            client.post(
                f"/api/drafts/{draft_id}/otp/verify", json={"code": entry}, headers=headers
            ).text
        )
    bodies.append(client.get(f"/api/drafts/{draft_id}", headers=headers).text)
    assert '"status":"verified"' in bodies[-1]

    raw = "\n".join(r.getMessage() for r in caplog.records)
    printed = capsys.readouterr()
    logs = raw + _formatted(list(caplog.records)) + printed.out + printed.err
    assert "otp send" in logs and "0780****234" in logs  # the masked line is there
    key = get_settings().otpiq_api_key
    for secret in (code, wrong, phone, "9647809871234", key):
        assert secret not in logs
    for body in bodies:
        assert code not in body

    for row in db.execute(select(OtpChallenge)).scalars():
        stored = " ".join(str(v) for v in (row.code_hash, row.context_hash, row.phone))
        assert code not in stored
    fake.outbox.clear()


def test_submission_never_logs_card_data(
    client, db, make_user, caplog, capsys, tmp_path, monkeypatch
) -> None:
    """Feature 008 (T045, FR-020): a submission and a refusal log and audit no national ID,
    family number, full phone, name or OTP code."""

    from sqlalchemy import select

    from app.models import AuditLog
    from app.services.card_reader_fake_data import FAMILY, FRONT_FIELDS, NID
    from app.services.otp_sender import get_otp_sender
    from tests.helpers.submit import complete_draft, make_catalog, marketer_headers, submit

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    caplog.set_level(logging.DEBUG)
    sender = get_otp_sender()
    sender.outbox.clear()
    catalog = make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))
    phone = "07801239876"

    h = marketer_headers(client, make_user("marketer"))
    assert submit(client, h, complete_draft(client, h, catalog, phone=phone)).status_code == 201
    other = marketer_headers(client, make_user("marketer"))
    # The same phone in a second draft: «تحقّق» is refused, then a submission is refused too.
    refused = complete_draft(client, other, catalog, phone=phone, verified=False)
    client.post(f"/api/drafts/{refused}/otp/send", headers=other)
    codes = [code for _, code in sender.outbox]

    raw = "\n".join(r.getMessage() for r in caplog.records)
    printed = capsys.readouterr()
    everything = raw + _formatted(list(caplog.records)) + printed.out + printed.err
    audits = db.scalars(select(AuditLog).where(AuditLog.action.like("request.%"))).all()
    blob = json.dumps([[a.before, a.after] for a in audits], ensure_ascii=False)
    assert "submit draft=" in everything and "result=approved" in everything
    secrets = [NID, FAMILY, phone, *codes, FRONT_FIELDS["name"], FRONT_FIELDS["last"]]
    for secret in secrets:
        assert secret not in everything, secret
        assert secret not in blob, secret


def test_existing_subscriber_paths_never_log_card_data(
    client, db, make_user, caplog, capsys, tmp_path, monkeypatch
) -> None:
    """Feature 009 (T045): the return, conflict, OTP precheck and contact-admin paths log no card
    number, phone or name, of either the draft or the matched record."""
    from app.services.card_reader_fake_data import FAMILY, NID
    from tests.helpers.requests import request_factory
    from tests.helpers.submit import (
        complete_draft,
        make_catalog,
        marketer_headers,
        patch,
        submit,
        verify,
    )

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    catalog = make_catalog(client, auth_header(login(client, make_user("super_admin").phone)))
    h = marketer_headers(client, make_user("marketer"))
    old = request_factory(
        db,
        make_user("marketer"),
        national_id=NID,
        national_id_input=NID,
        family_number=FAMILY,
        phone="07709990004",
        full_name="اسم سابق سري للسجل",
    )
    caplog.set_level(logging.DEBUG)

    draft_id = complete_draft(client, h, catalog, verified=False, phone="07709990004")
    client.post(f"/api/drafts/{draft_id}/otp/send", headers=h)  # the person's own phone
    patch(client, h, draft_id, {"return_chosen": True})
    client.post(f"/api/drafts/{draft_id}/contact-admin", headers=h)
    verify(client, h, draft_id)
    submit(client, h, draft_id)

    raw = "\n".join(r.getMessage() for r in caplog.records)
    printed = capsys.readouterr()
    everything = raw + _formatted(list(caplog.records)) + printed.out + printed.err
    for secret in (NID, FAMILY, "07709990004", old.full_name, old.username):
        assert secret not in everything


def test_review_decisions_never_log_card_data(client, db, make_user, caplog, capsys) -> None:
    """Feature 010 (T038): accept, reject and the review file log only the number and the action."""
    from tests.helpers.requests import request_factory

    marketer = make_user("marketer")
    h = auth_header(login(client, make_user("super_admin").phone))
    one = request_factory(db, marketer, status="pending_review", full_name="اسم سري للوغ أ")
    two = request_factory(db, marketer, status="pending_review", full_name="اسم سري للوغ ب")
    caplog.set_level(logging.DEBUG)

    client.get(f"/api/admin/requests/{one.id}", headers=h)
    client.post(f"/api/admin/requests/{one.id}/accept", json={}, headers=h)
    client.post(
        f"/api/admin/requests/{two.id}/reject",
        json={"reason": "other", "note": "طلب مكرر"},
        headers=h,
    )

    raw = "\n".join(r.getMessage() for r in caplog.records)
    printed = capsys.readouterr()
    everything = raw + _formatted(list(caplog.records)) + printed.out + printed.err
    assert "review accept" in raw and "review reject" in raw
    for request in (one, two):
        for secret in (
            request.national_id,
            request.family_number,
            request.phone,
            request.full_name,
        ):
            assert secret not in everything, secret
    assert "طلب مكرر" not in everything  # the note is for the marketer, not the logs


def test_a_pin_never_logs_the_values(client, db, make_user, caplog, capsys) -> None:
    """Feature 010 (T048): a pin logs the number, the field and the source, never a value."""
    from tests.helpers.review import pending_request

    marketer = make_user("marketer")
    h = auth_header(login(client, make_user("super_admin").phone))
    request = pending_request(
        db,
        marketer,
        [("numbers_edited", None, {"fields": ["national_id", "family_number"]})],
        full_name="اسم سري لتثبيت اللوغ",
        card_fields={"family_number": {"original": "5555E0000000000001", "edited": True}},
    )
    old = (request.national_id, request.family_number)
    caplog.set_level(logging.DEBUG)

    client.post(
        f"/api/admin/requests/{request.id}/pin",
        json={"field": "family_number", "source": "reading"},
        headers=h,
    )
    client.post(
        f"/api/admin/requests/{request.id}/pin",
        json={"field": "national_id", "source": "typed", "value": "199066667777"},
        headers=h,
    )

    raw = "\n".join(r.getMessage() for r in caplog.records)
    printed = capsys.readouterr()
    everything = raw + _formatted(list(caplog.records)) + printed.out + printed.err
    assert raw.count("review pin") == 2
    for secret in (
        *old,
        "5555E0000000000001",
        "199066667777",
        request.phone,
        request.full_name,
    ):
        assert secret not in everything, secret


def test_deletion_never_logs_personal_data(
    client, db, make_user, caplog, capsys, tmp_path, monkeypatch
) -> None:
    """specs/011 FR-020: the deletion logs the request number and the reason only."""
    from tests.helpers.requests import add_images, request_factory
    from tests.helpers.review import admin_with, headers_for

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    caplog.set_level(logging.DEBUG)
    marketer = make_user("marketer")
    request = request_factory(
        db,
        marketer,
        status="pending_review",
        full_name="اسم سري للحذف",
        address="عنوان سري للحذف",
        landmark="نقطة سرية للحذف",
    )
    images = add_images(db, request, tmp_path)
    secrets = [
        request.full_name,
        request.national_id,
        request.family_number,
        request.phone,
        request.username,
        request.address,
        request.landmark,
        str(request.location_lat),
        *(i.file_name for i in images),
    ]
    admin = admin_with(make_user, "review", "delete")
    res = client.post(
        f"/api/admin/requests/{request.id}/delete",
        json={"reason": "test", "confirm_number": request.number_label},
        headers=headers_for(client, admin),
    )
    assert res.status_code == 200, res.text

    printed = capsys.readouterr()
    raw = "\n".join(r.getMessage() for r in caplog.records)
    everything = raw + _formatted(list(caplog.records)) + printed.out + printed.err
    assert f"number={request.number}" in raw
    for secret in secrets:
        assert secret not in everything, secret


def test_notifications_and_link_message_never_log_personal_data(
    client, db, make_user, caplog, capsys
) -> None:
    """specs/012 T053: a notification logs its kind and the request number only; reading the
    notifications, the link message or a search logs no name, phone, number or address."""
    from tests.helpers.requests import request_factory
    from tests.helpers.review import admin_with, headers_for
    from tests.helpers.submit import marketer_headers

    marketer = make_user("marketer")
    one = request_factory(
        db,
        marketer,
        status="pending_review",
        full_name="اسم سري للإشعار أ",
        address="عنوان سري للإشعار",
        landmark="نقطة سرية للإشعار",
    )
    two = request_factory(db, marketer, status="pending_review", full_name="اسم سري للإشعار ب")
    caplog.set_level(logging.DEBUG)

    admin = headers_for(client, admin_with(make_user, "review"))
    client.post(f"/api/admin/requests/{one.id}/accept", json={}, headers=admin)
    client.post(
        f"/api/admin/requests/{two.id}/reject",
        json={"reason": "other", "note": "ملاحظة سرية للإشعار"},
        headers=admin,
    )
    h = marketer_headers(client, marketer)
    assert client.get("/api/notifications", headers=h).status_code == 200
    assert client.get(f"/api/requests/{one.id}", headers=h).json()["link_message"]
    client.get("/api/requests", params={"q": "اسم سري"}, headers=h)
    client.get("/api/requests", params={"q": one.phone}, headers=h)

    # The test client's own `httpx` lines are not server logs; the server's access line for the
    # same URL is checked through the production filter in the next test.
    records = [r for r in caplog.records if r.name != "httpx"]
    raw = "\n".join(r.getMessage() for r in records)
    printed = capsys.readouterr()
    everything = raw + _formatted(records) + printed.out + printed.err
    assert f"notification approved number={one.number}" in raw
    assert f"notification rejected number={two.number}" in raw
    for request in (one, two):
        for secret in (
            request.national_id,
            request.family_number,
            request.phone,
            request.full_name,
            request.username,
        ):
            assert secret not in everything, secret
    for secret in ("عنوان سري للإشعار", "نقطة سرية للإشعار", "ملاحظة سرية للإشعار", "اسم سري"):
        assert secret not in everything, secret


def test_the_search_text_never_reaches_the_access_log() -> None:
    """specs/012 T053: uvicorn's access line carries the full URL; the search box text (a phone or
    a name) is hidden, the rest of the line stays readable."""
    from urllib.parse import quote

    name = quote("اسم سري للبحث")
    for url, kept in (
        ("/api/requests?q=07801234567", "/api/requests?q="),
        (f"/api/requests?status=approved&q={name}", "/api/requests?status=approved&q="),
        (f"/api/requests?q={name}&status=linked", "&status=linked"),
    ):
        record = logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            __file__,
            1,
            '%s - "GET %s HTTP/1.1" %d',
            ("127.0.0.1:5000", url, 200),
            None,
        )
        line = _formatted([record])
        assert "07801234567" not in line and name not in line, line
        assert kept in line and "q=[REDACTED]" in line, line


def test_the_legacy_import_never_logs_personal_data(
    client, db, make_user, caplog, capsys, tmp_path, monkeypatch
) -> None:
    """specs/014 FR-009, Principle II: the import, its image fetching, the check against legacy
    subscribers, the review file and a legacy image open log ids and counts only."""
    from pathlib import Path

    from sqlalchemy import select

    from app.models import LegacyImage, LegacySubscriber, RequestReason
    from app.services import drive_fetcher, match_service
    from tests.helpers.review import admin_with, headers_for, pending_request

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    caplog.set_level(logging.DEBUG)
    sample = (
        Path(__file__).parent.parent / "fixtures" / "legacy" / "legacy_sample.csv"
    ).read_bytes()
    url = "/api/admin/imports/legacy/previews"
    reporter = admin_with(make_user, "reports")
    h = headers_for(client, reporter)

    preview = client.post(url, files={"file": ("legacy.csv", sample, "text/csv")}, headers=h).json()
    pid = preview["id"]
    choices = [{"index": i, "choice": "import"} for i in (4, 5, 7, 8, 9, 11, 13)] + [
        {"index": 12, "choice": "skip"},
        {"index": 14, "choice": "skip"},
        {"index": 6, "choice": "correct", "family_number": "1111A0000000000006"},
    ]
    assert (
        client.put(f"{url}/{pid}/choices", json={"choices": choices}, headers=h).status_code == 200
    )
    assert client.post(f"{url}/{pid}/confirm", headers=h).status_code == 201
    # A re-upload, and the Google adapter failing on the network.
    client.post(url, files={"file": ("legacy.csv", sample, "text/csv")}, headers=h)
    google = drive_fetcher.GoogleFetcher(
        client=drive_fetcher.httpx.Client(
            transport=drive_fetcher.httpx.MockTransport(lambda r: drive_fetcher.httpx.Response(500))
        )
    )
    google.fetch("fake-ok-f-0002")

    # The check, the review file and a legacy image open.
    match_service.find_matches(db, phone="07811110002", family_key="1111A0000000000004")
    sub = db.scalars(
        select(LegacySubscriber).where(LegacySubscriber.legacy_number == "T3C-001")
    ).one()
    request = pending_request(db, make_user("marketer"), [])
    db.add(
        RequestReason(
            request_id=request.id,
            reason="family_exists",
            matched_source="legacy",
            matched_ref=str(sub.id),
            details={},
        )
    )
    db.flush()
    reviewer = headers_for(client, admin_with(make_user, "review"))
    assert client.get(f"/api/admin/requests/{request.id}", headers=reviewer).status_code == 200
    image = db.scalars(
        select(LegacyImage).where(LegacyImage.legacy_subscriber_id == sub.id)
    ).first()
    assert client.get(f"/api/admin/legacy-images/{image.id}", headers=reviewer).status_code == 200

    printed = capsys.readouterr()
    raw = "\n".join(r.getMessage() for r in caplog.records)
    everything = raw + _formatted(list(caplog.records)) + printed.out + printed.err
    assert "legacy import confirmed" in raw
    for secret in (
        "07811110002",
        "0781111",
        "1111A0000000000004",
        "1111a00000000000o4",
        "1111A0000000000006",
        "سمير",
        "عينة",
        "sample@example.com",
        "fake-ok-f-0002",
        "fake-private-0011",
        image.file_name,
    ):
        assert secret not in everything, secret
