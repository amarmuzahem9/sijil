"""«فتح طلب برقمه»: find any submitted request by its number (specs/011 US6: FR-022; research R6,
R8). Synthetic data only."""

from urllib.parse import quote

import pytest

from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for


@pytest.fixture
def marketer(make_user):
    return make_user("marketer")


@pytest.fixture
def reviewer(make_user):
    return admin_with(make_user, "review")


def _find(client, h, text: str):
    return client.get(f"/api/admin/requests/by-number/{quote(text, safe='')}", headers=h)


def _arabic_indic(n: int) -> str:
    return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))


@pytest.mark.parametrize("status", ["pending_review", "approved", "rejected", "linked"])
def test_every_status_is_found(client, db, marketer, reviewer, status) -> None:
    request = request_factory(db, marketer, status=status)
    res = _find(client, headers_for(client, reviewer), request.number_label)
    assert res.status_code == 200, res.json()
    assert res.json() == {"id": request.id}


def test_a_deleted_request_is_found(client, db, marketer, reviewer) -> None:
    request = mark_deleted(db, request_factory(db, marketer, status="rejected"), reviewer)
    assert _find(client, headers_for(client, reviewer), str(request.number)).json() == {
        "id": request.id
    }


@pytest.mark.parametrize("typed", ["T3C-{n}", "t3c-{n}", "#T3C-{n}", "{n}", " {n} ", "ar"])
def test_number_formats(client, db, marketer, reviewer, typed) -> None:
    request = request_factory(db, marketer, status="pending_review")
    text = _arabic_indic(request.number) if typed == "ar" else typed.format(n=request.number)
    res = _find(client, headers_for(client, reviewer), text)
    assert res.json() == {"id": request.id}


@pytest.mark.parametrize("text", ["999999", "T3C-999999", "abc", "T3C-", "10a5"])
def test_unknown_or_unparsable_is_404(client, reviewer, text) -> None:
    res = _find(client, headers_for(client, reviewer), text)
    assert res.status_code == 404
    assert res.json() == {"code": "request_not_found", "message": "لا يوجد طلب بهذا الرقم"}


@pytest.mark.parametrize("perms", [(), ("delete",), ("link", "settings", "reports")])
def test_without_review_is_the_same_404(client, db, marketer, make_user, perms) -> None:
    request = request_factory(db, marketer, status="pending_review")
    res = _find(client, headers_for(client, admin_with(make_user, *perms)), request.number_label)
    assert res.status_code == 404
    assert res.json()["code"] == "request_not_found"


def test_marketer_is_refused(client, db, marketer) -> None:
    request = request_factory(db, marketer, status="pending_review")
    res = _find(client, headers_for(client, marketer), request.number_label)
    assert res.status_code in (403, 404)


def test_main_admin_finds(client, db, marketer, make_user) -> None:
    request = request_factory(db, marketer, status="pending_review")
    res = _find(client, headers_for(client, make_user("super_admin")), request.number_label)
    assert res.json() == {"id": request.id}


@pytest.mark.parametrize("text", ["T3C-005", "T3C-109", "t3c-001", "005"])
def test_a_legacy_number_opens_no_request(client, db, reviewer, make_user, text) -> None:
    """specs/014 FR-018: legacy numbers T3C-001 … T3C-109 are not request numbers (§7.3)."""
    from tests.helpers.legacy import legacy_subscriber

    legacy_subscriber(db, make_user("super_admin"), legacy_number="T3C-005")
    legacy_subscriber(db, make_user("super_admin"), legacy_number="T3C-109")
    res = _find(client, headers_for(client, reviewer), text)
    assert res.status_code == 404
    assert res.json()["code"] == "request_not_found"
