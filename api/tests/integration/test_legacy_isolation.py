"""Legacy subscribers stay out of requests, counters, commissions and notifications (specs/014 US4:
FR-017, SC-005). The import runs through the API with the synthetic file; every list and count
the admins and the marketer see is compared before and after. Synthetic data only."""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import Notification, Request
from tests.helpers.requests import request_factory
from tests.helpers.review import admin_with, headers_for
from tests.helpers.submit import marketer_headers
from tests.integration.test_legacy_confirm import CHOICES
from tests.integration.test_legacy_preview import URL, _ready


@pytest.fixture
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


def _snapshot(client, admin_h, marketer_h) -> dict:
    paths = {
        "admin_home": ("/api/admin/home", admin_h),
        "pending": ("/api/admin/requests/pending", admin_h),
        "awaiting": ("/api/admin/links/awaiting", admin_h),
        "recent": ("/api/admin/links/recent", admin_h),
        "dashboard": ("/api/marketer/dashboard", marketer_h),
        "requests": ("/api/requests", marketer_h),
        "unread": ("/api/notifications/unread-count", marketer_h),
        "notifications": ("/api/notifications", marketer_h),
    }
    out = {}
    for name, (path, h) in paths.items():
        res = client.get(path, headers=h)
        assert res.status_code == 200, (name, res.json())
        out[name] = res.json()
    return out


def test_an_import_changes_no_list_count_or_notification(client, db, make_user, uploads) -> None:
    main = make_user("super_admin")
    marketer = make_user("marketer")
    # Requests in every status; one shares a phone with the legacy file (T3C-001).
    request_factory(db, marketer, status="pending_review", phone="07811110002")
    request_factory(db, marketer, status="approved")
    request_factory(db, marketer, status="linked")
    request_factory(db, marketer, status="rejected")
    admin_h = headers_for(client, main)
    marketer_h = marketer_headers(client, marketer)
    notifications = db.scalar(select(func.count()).select_from(Notification))
    requests = db.scalar(select(func.count()).select_from(Request))
    before = _snapshot(client, admin_h, marketer_h)

    reporter = admin_with(make_user, "reports")
    preview = _ready(client, reporter)
    choices = [c for c in CHOICES] + [{"index": 2, "choice": "import"}]  # row 2 is now in_sijil
    res = client.put(
        f"{URL}/{preview['id']}/choices",
        json={"choices": choices},
        headers=headers_for(client, reporter),
    )
    assert res.status_code == 200, res.json()
    done = client.post(f"{URL}/{preview['id']}/confirm", headers=headers_for(client, reporter))
    assert done.status_code == 201, done.json()
    assert done.json()["imported"] == 11

    assert _snapshot(client, admin_h, marketer_h) == before
    assert db.scalar(select(func.count()).select_from(Notification)) == notifications
    assert db.scalar(select(func.count()).select_from(Request)) == requests
