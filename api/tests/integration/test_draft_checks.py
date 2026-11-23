"""Early warnings in every draft response (specs/008 US6, T041; FR-007, FR-008, SC-006).

Booleans and item codes only: the response never names who matched.
"""

import uuid

import pytest

from tests.conftest import auth_header, login
from tests.helpers.requests import request_factory

PHONE = "07801112233"
NID = "199811112222"
FAM = "7777A0000000000001"


@pytest.fixture
def h(client, make_user):
    headers = auth_header(login(client, make_user("marketer").phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    return headers


@pytest.fixture
def existing(db, make_user):
    return request_factory(
        db,
        make_user("marketer"),
        phone=PHONE,
        national_id=NID,
        national_id_input=NID,
        family_number=FAM,
        full_name="اسم مطابق سري",
    )


def _put(client, h, changes):
    draft_id = str(uuid.uuid4())
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": changes}, headers=h)
    assert res.status_code == 201, res.json()
    return draft_id, res.json()


def _patch(client, h, draft_id, changes):
    version = client.get(f"/api/drafts/{draft_id}", headers=h).json()["version"]
    res = client.patch(
        f"/api/drafts/{draft_id}", json={"version": version, "changes": changes}, headers=h
    )
    assert res.status_code == 200, res.json()
    return res.json()


# The same person (v1.10, specs/009) is the national ID with the family number of the same record,
# so the national-ID case starts with that family number on the draft.
CASES = [
    ("phone_input", "+964 780 111 2233", "phone_used", "phone_used", {}),
    (
        "national_id",
        "١٩٩٨١١١١٢٢٢٢",
        "national_id_exists",
        "national_id_exists",
        {"family_number": FAM},
    ),
    ("family_number", "7777 a 0000000000001", "family_exists", "family_exists_unconfirmed", {}),
]


@pytest.mark.parametrize(
    ("field", "value", "flag", "item", "base"), CASES, ids=[c[2] for c in CASES]
)
def test_each_key_warns_after_put_patch_and_get(
    client, h, existing, field, value, flag, item, base
):
    draft_id, put = _put(client, h, {**base, field: value})
    assert put["checks"][flag] is True
    assert item in [m["field"] for m in put["missing"]]

    got = client.get(f"/api/drafts/{draft_id}", headers=h).json()
    assert got["checks"][flag] is True

    cleared = _patch(client, h, draft_id, {field: None})
    assert cleared["checks"][flag] is False
    assert item not in [m["field"] for m in cleared["missing"]]

    again = _patch(client, h, draft_id, {field: value})
    assert again["checks"][flag] is True


def test_no_match_means_no_warning(client, h, existing):
    _, put = _put(client, h, {"phone_input": "07809998877", "national_id": "199800000001"})
    assert put["checks"] == {
        "phone_used": False,
        "national_id_exists": False,
        "id_conflict": False,
        "family_exists": False,
        "additional_confirmed": False,
        "return_available": False,
        "return_basis": None,
        "return_chosen": False,
        "return_pending": False,
    }


def test_warnings_never_name_the_other_subscriber(client, h, existing):
    draft_id, _ = _put(client, h, {"phone_input": PHONE, "national_id": NID, "family_number": FAM})
    text = client.get(f"/api/drafts/{draft_id}", headers=h).text
    for secret in (
        existing.full_name,
        existing.username,
        existing.tower_code,
        f"T3C-{existing.number}",
        f'"id": {existing.id}',
        str(existing.draft_id),
    ):
        assert secret not in text


def test_drafts_list_counts_the_warnings(client, h, existing):
    _put(client, h, {"phone_input": PHONE})
    clean_id, clean = _put(client, h, {"phone_input": "07809998877"})
    items = {i["id"]: i for i in client.get("/api/drafts", headers=h).json()["items"]}
    counts = sorted(i["missing_count"] for i in items.values())
    assert counts == [len(clean["missing"]), len(clean["missing"]) + 1]
