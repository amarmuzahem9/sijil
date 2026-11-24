"""Search in the marketer's own requests: `GET /api/requests?q=` (specs/012 US3, FR-013, FR-014;
contracts/api.md). Synthetic data only."""

import pytest

from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with
from tests.helpers.submit import marketer_headers

LIST = "/api/requests"


@pytest.fixture
def me(make_user):
    return make_user("marketer")


@pytest.fixture
def h(client, me):
    return marketer_headers(client, me)


def _ids(client, h, **params) -> list[int]:
    res = client.get(LIST, params=params, headers=h)
    assert res.status_code == 200, res.json()
    return [item["id"] for item in res.json()["items"]]


@pytest.fixture
def mine(db, me):
    return {
        "pending": request_factory(
            db, me, status="pending_review", full_name="أحمد علي حسين", phone="07801110001"
        ),
        "approved": request_factory(
            db, me, status="approved", full_name="سارة أحمد كريم", phone="07801110002"
        ),
        "rejected": request_factory(
            db, me, status="rejected", full_name="علي حسن جابر", phone="07801110003"
        ),
        "linked": request_factory(
            db, me, status="linked", full_name="زينب علي محمد", phone="07801110004"
        ),
    }


def test_name_matches_across_statuses(client, h, mine) -> None:
    found = _ids(client, h, q="أحمد")
    assert set(found) == {mine["pending"].id, mine["approved"].id}
    assert set(_ids(client, h, q="علي")) == {
        mine["pending"].id,
        mine["rejected"].id,
        mine["linked"].id,
    }


def test_name_ignores_diacritics_and_extra_spaces(client, h, mine) -> None:
    assert _ids(client, h, q="  أَحمد   علي ") == [mine["pending"].id]


def test_phone_in_any_form(client, h, mine) -> None:
    for q in ("07801110003", "0780 111 0003", "+964 780 111 0003", "٠٧٨٠١١١٠٠٠٣"):
        assert _ids(client, h, q=q) == [mine["rejected"].id], q


def test_number_with_or_without_prefix(client, h, mine) -> None:
    request = mine["linked"]
    arabic = str(request.number).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
    for q in (str(request.number), request.number_label, f"#{request.number_label}", arabic):
        assert _ids(client, h, q=q) == [request.id], q


def test_status_filter_still_applies(client, h, mine) -> None:
    assert _ids(client, h, q="علي", status="linked") == [mine["linked"].id]


def test_never_another_marketers_request(client, db, h, make_user, mine) -> None:
    theirs = request_factory(
        db, make_user("marketer"), full_name="أحمد غريب جداً", phone="07801119999"
    )
    for q in ("غريب", "07801119999", theirs.number_label):
        assert _ids(client, h, q=q) == [], q


def test_deleted_is_found_by_number_only(client, db, h, make_user, me) -> None:
    request = request_factory(
        db, me, status="pending_review", full_name="مشترك محذوف تجريبي", phone="07801118888"
    )
    mark_deleted(db, request, admin_with(make_user, "review", "delete"))
    assert _ids(client, h, q="محذوف") == []
    assert _ids(client, h, q="07801118888") == []
    res = client.get(LIST, params={"q": request.number_label}, headers=h)
    (item,) = res.json()["items"]
    assert (item["id"], item["full_name"], item["deletion_label"]) == (
        request.id,
        None,
        "طلب تجريبي",
    )


@pytest.mark.parametrize("q", ["ت", " ", "a"])
def test_too_short_is_422(client, h, q) -> None:
    res = client.get(LIST, params={"q": q}, headers=h)
    assert (res.status_code, res.json()["code"]) == (422, "validation_error")


def test_text_that_is_nothing_finds_nothing(client, h, mine) -> None:
    assert _ids(client, h, q="%%") == []
    assert _ids(client, h, q="ahmed") == []
