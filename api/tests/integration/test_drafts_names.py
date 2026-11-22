"""Name fields of the ministry form (docs/system.md §5.1 v1.5, specs/005 research.md R12)."""

import uuid

import pytest

from tests.conftest import auth_header, login

NAMES = {
    "first_name": "مشترك",
    "father_name": "تجريبي",
    "grandfather_name": "اختبار",
    "great_grandfather_name": "نموذج",
    "surname": "الوهمي",
    "mother_first_name": "أم",
    "mother_second_name": "تجريبية",
    "mother_third_name": "ثالث",
    "mother_surname": "اللقب",
}
REQUIRED = list(NAMES)[:7]
OPTIONAL = ["mother_third_name", "mother_surname"]


@pytest.fixture
def h(client, make_user):
    headers = auth_header(login(client, make_user("marketer").phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    return headers


def _create(client, h, changes=None) -> tuple[str, dict]:
    draft_id = str(uuid.uuid4())
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": changes or {}}, headers=h)
    assert res.status_code == 201, res.json()
    return draft_id, res.json()


def _patch(client, h, draft_id, version, changes):
    return client.patch(
        f"/api/drafts/{draft_id}", json={"version": version, "changes": changes}, headers=h
    )


@pytest.mark.parametrize("field", list(NAMES))
def test_each_name_field_autosaves(client, h, field):
    draft_id, _ = _create(client, h)
    res = _patch(client, h, draft_id, 1, {field: "  عبد   الله  "})
    assert res.status_code == 200
    assert res.json()[field] == "عبد الله"
    assert client.get(f"/api/drafts/{draft_id}", headers=h).json()[field] == "عبد الله"


def test_draft_restores_all_names(client, h):
    draft_id, _ = _create(client, h, NAMES)
    body = client.get(f"/api/drafts/{draft_id}", headers=h).json()
    for field, value in NAMES.items():
        assert body[field] == value
    missing = {m["field"] for m in body["missing"]}
    assert not missing & set(NAMES)


def test_full_name_is_computed_from_the_first_five(client, h):
    draft_id, body = _create(client, h, NAMES)
    assert body["full_name"] == "مشترك تجريبي اختبار نموذج الوهمي"
    # Mother's names never enter full_name; empty parts are skipped.
    body = _patch(
        client, h, draft_id, 1, {"grandfather_name": None, "mother_first_name": "أخرى"}
    ).json()
    assert body["full_name"] == "مشترك تجريبي نموذج الوهمي"
    body = _patch(client, h, draft_id, 2, {f: None for f in list(NAMES)[:5]}).json()
    assert body["full_name"] is None


def test_full_name_cannot_be_sent(client, h):
    draft_id, _ = _create(client, h)
    res = _patch(client, h, draft_id, 1, {"full_name": "اسم مزوّر"})
    assert res.status_code == 422


@pytest.mark.parametrize("value", ["علي2", "٣علي", "Ali", "علي A", "علي-حسن", "م.علي"])
def test_digits_and_non_arabic_letters_are_refused_and_not_saved(client, h, value):
    draft_id, _ = _create(client, h, {"first_name": "مشترك"})
    res = _patch(client, h, draft_id, 1, {"first_name": value, "address": "حي"})
    assert res.status_code == 422
    assert res.json() == {
        "code": "invalid_name_text",
        "message": "الاسم أحرف عربية فقط",
        "field": "first_name",
    }
    body = client.get(f"/api/drafts/{draft_id}", headers=h).json()
    assert body["first_name"] == "مشترك"
    assert body["address"] is None  # the whole save was refused
    assert body["version"] == 1


def test_create_with_a_bad_name_is_refused(client, h):
    draft_id = str(uuid.uuid4())
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": {"surname": "X1"}}, headers=h)
    assert res.status_code == 422
    assert res.json()["field"] == "surname"
    assert client.get(f"/api/drafts/{draft_id}", headers=h).status_code == 404


def test_diacritics_and_tatweel_are_removed(client, h):
    fatha, kasra, shadda, tatweel = chr(0x064E), chr(0x0650), chr(0x0651), chr(0x0640)
    draft_id, _ = _create(client, h)
    body = _patch(
        client, h, draft_id, 1, {"first_name": "ع" + fatha + "ل" + kasra + "ي" + shadda + tatweel}
    ).json()
    assert body["first_name"] == "علي"


def test_iraqi_letters_are_accepted(client, h):
    _, body = _create(client, h, {"father_name": "گاطع", "surname": "چاسب"})
    assert (body["father_name"], body["surname"]) == ("گاطع", "چاسب")


def test_over_50_characters_is_too_long(client, h):
    draft_id, _ = _create(client, h)
    res = _patch(client, h, draft_id, 1, {"surname": "ا" * 51})
    assert res.status_code == 422
    assert res.json()["code"] == "too_long" and res.json()["field"] == "surname"
    assert _patch(client, h, draft_id, 1, {"surname": "ا" * 50}).status_code == 200


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_optional_mother_fields_accept_empty(client, h, empty):
    required = {k: v for k, v in NAMES.items() if k in REQUIRED}
    draft_id, _ = _create(client, h, {**required, "mother_third_name": "ثالث"})
    body = _patch(client, h, draft_id, 1, {f: empty for f in OPTIONAL}).json()
    assert body["mother_third_name"] is None and body["mother_surname"] is None
    assert not {m["field"] for m in body["missing"]} & set(NAMES)


def test_each_missing_required_name_is_listed_by_name(client, h):
    _, body = _create(client, h, {"first_name": "مشترك", "surname": "الوهمي"})
    names_missing = [m["field"] for m in body["missing"] if m["field"] in NAMES]
    assert names_missing == [
        "father_name",
        "grandfather_name",
        "great_grandfather_name",
        "mother_first_name",
        "mother_second_name",
    ]


def test_list_and_search_use_full_name(client, h):
    _create(client, h, NAMES)
    _create(client, h, {"first_name": "آخر"})
    items = client.get("/api/drafts", headers=h).json()["items"]
    assert {i["full_name"] for i in items} == {"مشترك تجريبي اختبار نموذج الوهمي", "آخر"}
    found = client.get("/api/drafts", params={"q": "اختبار نموذج"}, headers=h).json()["items"]
    assert [i["full_name"] for i in found] == ["مشترك تجريبي اختبار نموذج الوهمي"]
    # The mother's names are not searched.
    assert client.get("/api/drafts", params={"q": "تجريبية"}, headers=h).json()["items"] == []
