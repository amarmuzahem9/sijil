"""«المشتركون» search (docs/system.md v1.24 §10 item 4; specs/018 US1, FR-001 to FR-006, FR-009,
FR-012; research R2–R4, R6, R11; contracts/api.md). Synthetic data only."""

import logging
from datetime import UTC, datetime, timedelta

import pytest

from app.services import subscriber_search
from tests.helpers.legacy import legacy_subscriber
from tests.helpers.requests import mark_deleted, request_factory
from tests.helpers.review import admin_with, headers_for
from tests.helpers.sas import sas_subscriber

URL = "/api/admin/subscribers"
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
P1, P2, P3 = "07815550001", "07815550002", "07815550003"
NID = "199055500001"
FAMILY = "1990S5550000000001"
ROW_KEYS = {
    "source",
    "ref",
    "number_label",
    "legacy_number",
    "full_name",
    "tower_name",
    "tower_code",
    "phone",
    "status",
    "registered_at",
    "deleted",
}


@pytest.fixture
def reviewer(make_user):
    return admin_with(make_user, "review")


@pytest.fixture
def world(db, make_user, reviewer):
    marketer = make_user("marketer")
    request = request_factory(
        db,
        marketer,
        status="linked",
        full_name="زينة بحثية تجريبية",
        phone=P1,
        national_id=NID,
        national_id_input=NID,
        family_number=FAMILY,
        submitted_at=T0 + timedelta(days=3),
    )
    rejected = request_factory(
        db,
        marketer,
        status="rejected",
        approved_at=None,
        full_name="زينة بحثية مرفوضة",
        submitted_at=T0 + timedelta(days=1),
    )
    legacy = legacy_subscriber(
        db,
        reviewer,
        full_name="زينه بحثيه قديمة",
        phone=P1,
        family_number=FAMILY,
        legacy_number="T3C-077",
        form_submitted_at=T0 - timedelta(days=300),
    )
    cancelled = legacy_subscriber(
        db, reviewer, full_name="زينة بحثية ملغاة", status_text="ملغي", legacy_number="T3C-078"
    )
    sas = sas_subscriber(
        db,
        reviewer,
        username=f"ZZT01-{P2}",
        full_name="زينة بحثية SAS",
        phone=P1,
        sas_created_at=T0 - timedelta(days=30),
    )
    sas_no_phone = sas_subscriber(db, reviewer, username=f"ZZT01-{P3}", phone=None)
    return {
        "request": request,
        "rejected": rejected,
        "legacy": legacy,
        "cancelled": cancelled,
        "sas": sas,
        "sas_no_phone": sas_no_phone,
    }


def _search(client, user, q, **params):
    res = client.get(URL, params={"q": q, **params}, headers=headers_for(client, user))
    return res


def _found(client, user, q) -> set[tuple[str, str]]:
    res = _search(client, user, q)
    assert res.status_code == 200, res.json()
    return {(r["source"], r["ref"]) for r in res.json()["items"]}


def _ref(source, obj):
    return (source, str(obj.id))


# --- each kind across the sources (FR-003) -------------------------------------------------------


def test_phone_finds_all_three_sources(client, world, reviewer) -> None:
    found = _found(client, reviewer, "0781 555 0001")
    assert found == {
        _ref("sijil", world["request"]),
        _ref("legacy", world["legacy"]),
        _ref("sas", world["sas"]),
    }


def test_the_phone_inside_a_sas_username(client, world, reviewer) -> None:
    assert _found(client, reviewer, P3) == {_ref("sas", world["sas_no_phone"])}
    assert _found(client, reviewer, P2) == {_ref("sas", world["sas"])}


def test_family_and_national_id(client, world, reviewer) -> None:
    assert _found(client, reviewer, "1990 s 5550000000001") == {
        _ref("sijil", world["request"]),
        _ref("legacy", world["legacy"]),
    }
    assert _found(client, reviewer, NID) == {_ref("sijil", world["request"])}


def test_username(client, world, reviewer) -> None:
    assert _found(client, reviewer, world["request"].username.lower()) == {
        _ref("sijil", world["request"])
    }
    assert _found(client, reviewer, f"zzt01-{P2}") == {_ref("sas", world["sas"])}


def test_name_with_other_spellings_across_sources(client, world, reviewer) -> None:
    found = _found(client, reviewer, "زينه بحثيه")
    assert found == {
        _ref("sijil", world["request"]),
        _ref("sijil", world["rejected"]),  # a rejected request is a record (§6.1)
        _ref("legacy", world["legacy"]),
        _ref("legacy", world["cancelled"]),  # «ملغي» does not count but is found (§12.1)
        _ref("sas", world["sas"]),
    }


def test_numbers(client, world, reviewer) -> None:
    assert _found(client, reviewer, world["request"].number_label) == {
        _ref("sijil", world["request"])
    }
    assert _found(client, reviewer, "t3c-077") == {_ref("legacy", world["legacy"])}


# --- rows, order, paging (FR-005) ----------------------------------------------------------------


def test_rows_keys_order_and_fields(client, world, reviewer) -> None:
    body = _search(client, reviewer, P1).json()
    assert body["kind"] == "phone"
    assert body["total"] == 3
    assert [r["source"] for r in body["items"]] == ["sijil", "sas", "legacy"]  # newest first
    for row in body["items"]:
        assert set(row) == ROW_KEYS
        assert row["deleted"] is False
    request_row, sas_row, legacy_row = body["items"]
    assert (request_row["status"], request_row["number_label"]) == (
        "linked",
        world["request"].number_label,
    )
    assert request_row["tower_code"] == world["request"].tower_code
    assert legacy_row["legacy_number"] == "T3C-077"
    assert legacy_row["status"] == "تم"
    assert sas_row["tower_code"] == "ZZT01"


def test_paging(client, db, reviewer) -> None:
    for i in range(55):
        sas_subscriber(
            db,
            reviewer,
            username=f"PGT01-0782{i:07d}",
            full_name="رقية صفحات تجريبية",
            sas_created_at=T0 - timedelta(days=i),
        )
    first = _search(client, reviewer, "رقيه صفحات").json()
    assert (first["total"], len(first["items"])) == (55, 50)
    second = _search(client, reviewer, "رقيه صفحات", offset=50).json()
    assert len(second["items"]) == 5
    assert not {r["ref"] for r in first["items"]} & {r["ref"] for r in second["items"]}


@pytest.mark.parametrize("q", ["اح", "%", "abc", ""])
def test_unclear_query(client, reviewer, q) -> None:
    res = _search(client, reviewer, q)
    assert (res.status_code, res.json()["code"]) == (422, "search_unclear")


# --- deleted requests (FR-006) -------------------------------------------------------------------


def test_deleted_by_number_only(client, db, make_user, reviewer) -> None:
    request = request_factory(
        db, make_user("marketer"), status="pending_review", approved_at=None, phone="07815550009"
    )
    label = request.number_label
    mark_deleted(db, request, reviewer)
    assert _found(client, reviewer, "07815550009") == set()
    (row,) = _search(client, reviewer, label).json()["items"]
    assert row == {
        "source": "sijil",
        "ref": str(request.id),
        "number_label": label,
        "legacy_number": None,
        "full_name": None,
        "tower_name": None,
        "tower_code": None,
        "phone": None,
        "status": None,
        "registered_at": None,
        "deleted": True,
    }


# --- permissions (FR-001, FR-009) ----------------------------------------------------------------


@pytest.mark.parametrize("permission", ["link", "reports"])
@pytest.mark.parametrize("q", [NID, "199000000000", FAMILY, "1990X0000000000000"])
def test_identity_search_refused_without_review(
    client, world, make_user, monkeypatch, permission, q
) -> None:
    """Refused before any lookup, so an existing and a made-up number answer the same."""

    def no_lookup(*_a, **_k):
        raise AssertionError("no lookup may run")

    monkeypatch.setattr(subscriber_search, "search", no_lookup)
    res = _search(client, admin_with(make_user, permission), q)
    assert (res.status_code, res.json()["code"]) == (403, "identity_search_forbidden")


@pytest.mark.parametrize("permission", ["link", "reports"])
def test_link_and_reports_search_other_kinds(client, world, make_user, permission) -> None:
    assert len(_found(client, admin_with(make_user, permission), P1)) == 3


def test_main_admin_searches_identity(client, world, make_user) -> None:
    assert _found(client, make_user("super_admin"), NID) == {_ref("sijil", world["request"])}


@pytest.mark.parametrize("permission", ["settings", "marketers", "commissions", "delete"])
def test_other_admins_refused(client, make_user, permission) -> None:
    res = _search(client, admin_with(make_user, permission), P1)
    assert (res.status_code, res.json()["code"]) == (403, "forbidden")


def test_marketer_refused(client, make_user) -> None:
    res = _search(client, make_user("marketer"), P1)
    assert (res.status_code, res.json()["code"]) == (403, "forbidden")


def test_without_session(client) -> None:
    assert client.get(URL, params={"q": P1}).status_code == 401


# --- logs (FR-012, research R11) -----------------------------------------------------------------


def test_logs_hold_kind_and_count_only(client, world, reviewer, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="sijil.subscribers"):
        _search(client, reviewer, P1)
        _search(client, reviewer, "زينه بحثيه")
    text = caplog.text
    assert "kind=phone" in text and "kind=name" in text
    for value in (P1, "0781", "زينه", "زينة", NID, world["request"].full_name):
        assert value not in text
