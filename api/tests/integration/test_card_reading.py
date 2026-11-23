"""US1 + US3: a reading fills the card fields; unclear photos ask for a re-shoot
(specs/006 data-model.md › Applying a `done` pair, research R6, R8; tasks T018, T033).

The upload queues the reading; tests run it inline with the fake reader (conftest). Images are
synthetic (tests/helpers/card_images.py), with made-up names and numbers.
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import ImageAccessLog
from app.services.card_reader_fake_data import FAMILY, NID
from tests.conftest import auth_header, login
from tests.helpers.card_images import scenario_jpeg


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


def _headers(client, user, cid: str | None = None) -> dict[str, str]:
    headers = auth_header(login(client, user.phone))
    headers["X-Client-Id"] = cid or str(uuid.uuid4())
    return headers


@pytest.fixture
def owner(client, make_user):
    user = make_user("marketer")
    return user, _headers(client, user)


def new_draft(client, headers) -> str:
    draft_id = str(uuid.uuid4())
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": {}}, headers=headers)
    assert res.status_code == 201
    return draft_id


def upload(client, headers, draft_id: str, side: str, scenario: str) -> dict:
    res = client.post(
        f"/api/drafts/{draft_id}/images/{side}",
        files={"file": (f"{side}.jpg", scenario_jpeg(scenario), "image/jpeg")},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


def read_card(client, headers, front="clear_front", back="clear_back") -> str:
    draft_id = new_draft(client, headers)
    upload(client, headers, draft_id, "front", front)
    upload(client, headers, draft_id, "back", back)
    return draft_id


def get(client, headers, draft_id: str) -> dict:
    res = client.get(f"/api/drafts/{draft_id}", headers=headers)
    assert res.status_code == 200
    return res.json()


EXPECTED = {
    "first_name": "مشترك",
    "father_name": "تجريبي",
    "grandfather_name": "اختبار",
    "surname": "الوهمي",
    "mother_first_name": "أم",
    "mother_second_name": "تجريبية",
    "national_id": NID,
    "family_number": FAMILY,
}


# --- US1: filling -------------------------------------------------------------------------------


def test_front_only_does_not_read(client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    body = upload(client, headers, draft_id, "front", "clear_front")
    assert body["card_reading"] == {
        "front": {"state": "pending", "reason": None, "finished_at": None, "surname_empty": None},
        "back": None,
    }
    assert body["first_name"] is None
    status = client.get(f"/api/drafts/{draft_id}/card-reading", headers=headers).json()
    assert status["front"]["state"] == "pending" and status["back"] is None


def test_clear_card_fills_the_eight_fields_with_marks(client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    upload(client, headers, draft_id, "front", "clear_front")
    after_front = get(client, headers, draft_id)["version"]
    upload(client, headers, draft_id, "back", "clear_back")
    body = get(client, headers, draft_id)

    for field, value in EXPECTED.items():
        assert body[field] == value, field
        mark = body["card_fields"][field]
        assert mark["source"] == "card"
        assert mark["original"] == value
        assert mark["from"] == ("back" if field == "family_number" else "front")
    assert body["card_fields"]["first_name"]["confidence"] == pytest.approx(0.97)
    # The fourth name and the mother's third name and surname are never on the card.
    for field in ("great_grandfather_name", "mother_third_name", "mother_surname"):
        assert body[field] is None and field not in body["card_fields"]
    assert body["full_name"] == "مشترك تجريبي اختبار الوهمي"
    assert body["card_reading"]["front"]["state"] == "done"
    assert body["card_reading"]["back"]["state"] == "done"
    # Upload of the back (+1) and applying the reading (+1).
    assert body["version"] == after_front + 2
    missing = {m["field"] for m in body["missing"]}
    assert not missing & set(EXPECTED)


def test_reading_counts_as_a_save_of_the_uploading_page(client, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers)
    status = client.get(f"/api/drafts/{draft_id}/card-reading", headers=headers).json()
    assert status["same_client"] is True
    other = {**headers, "X-Client-Id": str(uuid.uuid4())}
    assert (
        client.get(f"/api/drafts/{draft_id}/version", headers=other).json()["same_client"] is False
    )


def test_name_breaking_the_rule_is_left_empty_but_its_reading_is_kept(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, front="front_latin_name"))
    assert body["grandfather_name"] is None
    assert body["card_fields"]["grandfather_name"] == {
        "source": "card",
        "original": "Test",
        "confidence": pytest.approx(0.97),
        "from": "front",
    }
    assert "grandfather_name" in {m["field"] for m in body["missing"]}


def test_national_id_from_the_verified_mrz_when_the_front_has_none(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, front="front_no_id"))
    assert body["national_id"] == NID
    assert body["card_fields"]["national_id"]["from"] == "mrz"


def test_unverified_mrz_does_not_fill_the_national_id(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, "front_no_id", "back_unverified"))
    assert body["national_id"] is None


def test_family_number_with_letter_o_is_corrected(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, back="back_family_o"))
    assert body["family_number"] == "1064L00M1234567890"


def test_empty_surname_on_the_card_is_reported_not_chosen(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, front="front_no_surname"))
    assert body["surname"] is None
    assert body["no_surname"] is False
    assert body["card_reading"]["front"]["surname_empty"] is True
    assert "surname" in {m["field"] for m in body["missing"]}


def test_another_device_sees_the_reading(client, owner) -> None:
    user, headers = owner
    draft_id = read_card(client, headers)
    second = _headers(client, user)
    body = get(client, second, draft_id)
    assert body["first_name"] == "مشترك"
    assert body["card_fields"]["first_name"]["source"] == "card"


def test_reading_routes_are_owner_only(client, owner, make_user) -> None:
    _, headers = owner
    draft_id = read_card(client, headers)
    stranger = _headers(client, make_user("marketer"))
    res = client.get(f"/api/drafts/{draft_id}/card-reading", headers=stranger)
    assert res.status_code == 404
    assert res.json()["code"] == "draft_not_found"


def test_each_side_sent_to_the_reader_is_logged_as_ocr_access(client, db, owner) -> None:
    user, headers = owner
    draft_id = read_card(client, headers)
    rows = db.scalars(
        select(ImageAccessLog).where(ImageAccessLog.draft_id == uuid.UUID(draft_id))
    ).all()
    assert sorted((r.side, r.purpose, r.user_id) for r in rows) == [
        ("back", "ocr", user.id),
        ("front", "ocr", user.id),
    ]


def test_raw_reading_is_never_sent_to_the_page(client, owner) -> None:
    _, headers = owner
    body = client.get(f"/api/drafts/{read_card(client, headers)}", headers=headers).text
    assert "detections" not in body and "optional1" not in body and "raw" not in body


# --- US3: re-shoot ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "front,reason",
    [
        ("no_card", "no_card"),
        ("clear_back", "wrong_side"),
        ("other_document", "not_unified"),
        ("two_cards", "multiple"),
    ],
)
def test_unclear_front_asks_for_a_reshoot_and_fills_nothing_from_it(
    client, owner, front, reason
) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, front=front))
    assert body["card_reading"]["front"]["state"] == "reshoot"
    assert body["card_reading"]["front"]["reason"] == reason
    for field in ("first_name", "father_name", "surname"):
        assert body[field] is None
    # The back was read normally: its family number is applied (spec edge case).
    assert body["family_number"] == FAMILY
    assert body["card_fields"]["family_number"]["source"] == "card"


def test_same_card_detected_twice_is_read_normally(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, back="duplicate_back"))
    assert body["card_reading"]["back"]["state"] == "done"
    assert body["family_number"] == FAMILY


def test_reshoot_never_blocks_typing(client, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers, front="no_card")
    version = get(client, headers, draft_id)["version"]
    res = client.patch(
        f"/api/drafts/{draft_id}",
        json={"version": version, "changes": {"first_name": "مشترك"}},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["card_fields"]["first_name"]["source"] == "edited"


# --- US7: back fields (owner change, research R13) ----------------------------------------------

BACK_EXPECTED = {
    "birth_date": "1999-01-01",
    "birth_place": "حي تجريبي-بغداد",
    "issue_date": "2020-01-02",
    "expiry_date": "2030-01-01",
    "issuing_authority": "مديرية الجنسية والمعلومات المدنية",
}


def test_clear_back_fills_the_five_back_fields(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers))
    for field, value in BACK_EXPECTED.items():
        assert body[field] == value, field
        assert body["card_fields"][field]["source"] == "card", field
    assert body["card_fields"]["birth_date"]["from"] == "mrz"
    assert body["card_fields"]["issue_date"]["from"] == "back"
    # The misread authority is snapped; its original is the snapped text.
    assert (
        body["card_fields"]["issuing_authority"]["original"] == BACK_EXPECTED["issuing_authority"]
    )
    missing = {m["field"] for m in body["missing"]}
    assert not missing & {*BACK_EXPECTED, "card_expired"}


def test_printed_birth_date_when_the_mrz_birth_is_wrong(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, back="back_birth_print"))
    assert body["birth_date"] == "1999-01-01"
    assert body["card_fields"]["birth_date"]["from"] == "back"


def test_issue_date_that_does_not_match_stays_empty(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, back="back_issue_mismatch"))
    assert body["issue_date"] is None
    assert body["card_fields"]["issue_date"]["original"] == "2021/05/05"
    assert "issue_date" in {m["field"] for m in body["missing"]}
    assert body["expiry_date"] == "2030-01-01"


def test_expired_card_is_a_missing_item_but_saves(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, back="back_expired"))
    assert body["expiry_date"] == "2025-01-01"
    assert body["issue_date"] == "2015-01-02"
    assert {"field": "card_expired", "code": "card_expired"} in body["missing"]


def test_woman_born_after_2000(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, "front_female_2000", "back_2000"))
    assert body["first_name"] == "مشتركة"
    assert body["national_id"] == "200512345678"
    assert body["birth_date"] == "2005-03-14"
    assert body["national_id_check"] is None or not body["national_id_check"]["mismatch"]


# --- US5: the reader fails or is too slow (FR-014, contracts › retry) ----------------------------

from app.core.timeutil import utc_now  # noqa: E402
from app.models import CardReading  # noqa: E402
from app.services import card_reading_service  # noqa: E402
from app.services.card_reader import FakeCardReader  # noqa: E402


def test_reader_failure_then_retry(client, db, owner, monkeypatch) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    patch_body = {"version": 0, "changes": {"first_name": "مكتوب"}}
    patch_body["version"] = get(client, headers, draft_id)["version"]
    client.patch(f"/api/drafts/{draft_id}", json=patch_body, headers=headers)
    upload(client, headers, draft_id, "front", "clear_front")
    upload(client, headers, draft_id, "back", "reader_failure")
    body = get(client, headers, draft_id)
    assert body["card_reading"]["back"] == {
        "state": "failed",
        "reason": "unavailable",
        "finished_at": body["card_reading"]["back"]["finished_at"],
        "surname_empty": None,
    }
    assert body["first_name"] == "مكتوب"  # typed meanwhile, kept
    assert body["father_name"] == "تجريبي"  # the front was read

    # The reader is back: the fake reads the same photo as a clear back from now on.
    original = FakeCardReader.scenario_for
    monkeypatch.setattr(
        FakeCardReader,
        "scenario_for",
        lambda self, image, side: "clear_back" if side == "back" else original(self, image, side),
    )
    res = client.post(f"/api/drafts/{draft_id}/card-reading/retry", headers=headers)
    assert res.status_code == 202
    body = get(client, headers, draft_id)
    assert body["card_reading"]["back"]["state"] == "done"
    assert body["family_number"] == "1064L00M1234567890"
    assert body["first_name"] == "مكتوب"


def test_retry_needs_a_failed_side(client, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers)
    res = client.post(f"/api/drafts/{draft_id}/card-reading/retry", headers=headers)
    assert res.status_code == 409
    assert res.json()["code"] == "reading_not_retryable"


def test_retry_is_owner_only(client, owner, make_user) -> None:
    _, headers = owner
    draft_id = read_card(client, headers, back="reader_failure")
    stranger = _headers(client, make_user("marketer"))
    res = client.post(f"/api/drafts/{draft_id}/card-reading/retry", headers=stranger)
    assert res.status_code == 404


def test_slow_reader_times_out(client, db, owner, monkeypatch) -> None:
    _, headers = owner
    monkeypatch.setattr(FakeCardReader, "slow_seconds", 0.01)
    body = get(client, headers, read_card(client, headers, back="reader_slow"))
    assert (body["card_reading"]["back"]["state"], body["card_reading"]["back"]["reason"]) == (
        "failed",
        "timeout",
    )


def test_running_reading_older_than_the_limit_is_timed_out_on_status(client, db, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers)
    from datetime import timedelta

    reading = db.query(CardReading).filter_by(draft_id=uuid.UUID(draft_id), side="front").one()
    reading.state = "running"
    reading.started_at = utc_now() - timedelta(seconds=90)
    db.commit()
    status = client.get(f"/api/drafts/{draft_id}/card-reading", headers=headers).json()
    assert (status["front"]["state"], status["front"]["reason"]) == ("failed", "timeout")
    assert card_reading_service is not None


# --- US6: replacing an image reads only that side again (research R5) --------------------------


def test_replacing_the_front_reads_only_the_front(client, db, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers)
    upload(client, headers, draft_id, "front", "front_b")
    body = get(client, headers, draft_id)
    assert body["first_name"] == "سالم"
    assert body["family_number"] == "1064L00M1234567890"  # the back's reading is reused
    rows = db.scalars(
        select(ImageAccessLog).where(
            ImageAccessLog.draft_id == uuid.UUID(draft_id), ImageAccessLog.purpose == "ocr"
        )
    ).all()
    assert sorted(r.side for r in rows) == ["back", "front", "front"]


# --- feature 008: a read national ID that already exists (T042) -------------------------------


def test_read_national_id_that_exists_warns(client, db, owner, make_user) -> None:
    from tests.helpers.requests import request_factory

    request_factory(db, make_user("marketer"), national_id=NID, national_id_input=NID)
    _, headers = owner
    draft_id = read_card(client, headers)
    draft = client.get(f"/api/drafts/{draft_id}", headers=headers).json()
    assert draft["national_id"] == NID
    assert draft["checks"]["national_id_exists"] is True
    assert {"field": "national_id_exists", "code": "national_id_exists"} in draft["missing"]
