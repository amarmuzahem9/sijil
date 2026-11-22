"""US1 + US2: «لا يوجد لقب على البطاقة» and the edited marks that keep the original reading
(specs/006 data-model.md › Rules on save, research R8, R9; tasks T019, T029). Synthetic data.
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.services import card_reading_service
from app.services.card_reader import FakeCardReader
from tests.conftest import auth_header, login
from tests.integration.test_card_reading import get, new_draft, read_card, upload


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def owner(client, make_user):
    user = make_user("marketer")
    headers = auth_header(login(client, user.phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    return user, headers


def patch(client, headers, draft_id: str, changes: dict):
    version = get(client, headers, draft_id)["version"]
    return client.patch(
        f"/api/drafts/{draft_id}", json={"version": version, "changes": changes}, headers=headers
    )


# --- no surname (FR-017) ------------------------------------------------------------------------


def test_no_surname_clears_the_surname_and_satisfies_it(client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    patch(client, headers, draft_id, {"first_name": "مشترك", "surname": "الوهمي"})
    body = patch(client, headers, draft_id, {"no_surname": True}).json()
    assert body["no_surname"] is True
    assert body["surname"] is None
    assert body["full_name"] == "مشترك"
    assert body["card_fields"]["surname"]["source"] == "edited"
    assert "surname" not in {m["field"] for m in body["missing"]}


def test_typing_a_surname_clears_the_choice(client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    patch(client, headers, draft_id, {"no_surname": True})
    body = patch(client, headers, draft_id, {"surname": "الوهمي"}).json()
    assert body["no_surname"] is False
    assert body["surname"] == "الوهمي"


def test_no_surname_is_not_overwritten_by_a_reading(client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    patch(client, headers, draft_id, {"no_surname": True})
    upload(client, headers, draft_id, "front", "clear_front")
    upload(client, headers, draft_id, "back", "clear_back")
    body = get(client, headers, draft_id)
    assert body["no_surname"] is True and body["surname"] is None
    assert body["first_name"] == "مشترك"
    # The surname read from the card is still kept as its original reading.
    assert body["card_fields"]["surname"]["original"] == "الوهمي"


def test_no_surname_requires_an_empty_surname_in_the_database(db, client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    patch(client, headers, draft_id, {"surname": "الوهمي"})
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.execute(text("UPDATE drafts SET no_surname = true WHERE id = :id"), {"id": draft_id})


# --- edited marks (US2, FR-007–FR-009) ----------------------------------------------------------


def test_editing_a_read_field_keeps_the_original(client, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers)
    body = patch(client, headers, draft_id, {"grandfather_name": "مصحح"}).json()
    assert body["grandfather_name"] == "مصحح"
    assert body["card_fields"]["grandfather_name"] == {
        "source": "edited",
        "original": "اختبار",
        "confidence": pytest.approx(0.97),
        "from": "front",
    }
    assert body["card_fields"]["first_name"]["source"] == "card"


def test_clearing_a_read_field_counts_as_edited(client, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers)
    body = patch(client, headers, draft_id, {"father_name": None}).json()
    assert body["father_name"] is None
    assert body["card_fields"]["father_name"]["source"] == "edited"
    assert body["card_fields"]["father_name"]["original"] == "تجريبي"


def test_resending_the_same_value_changes_nothing(client, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers)
    body = patch(client, headers, draft_id, {"first_name": "مشترك"}).json()
    assert body["card_fields"]["first_name"]["source"] == "card"


def test_typed_value_before_the_reading_wins(client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    patch(client, headers, draft_id, {"national_id": "199900000001", "first_name": "مكتوب"})
    upload(client, headers, draft_id, "front", "clear_front")
    upload(client, headers, draft_id, "back", "clear_back")
    body = get(client, headers, draft_id)
    assert body["national_id"] == "199900000001"
    assert body["first_name"] == "مكتوب"
    assert body["card_fields"]["national_id"]["source"] == "edited"
    assert body["card_fields"]["national_id"]["original"] == "199912345678"
    assert body["father_name"] == "تجريبي"  # untouched fields are still filled


def test_reading_again_never_overwrites_an_edit(client, db, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers)
    patch(client, headers, draft_id, {"grandfather_name": "مصحح"})
    # The front is read again (e.g. after a retake), with another synthetic card.
    upload(client, headers, draft_id, "front", "front_b")
    body = get(client, headers, draft_id)
    assert body["grandfather_name"] == "مصحح"
    assert body["card_fields"]["grandfather_name"]["original"] == "ناصر"
    assert body["first_name"] == "سالم"  # unedited field takes the new reading


def test_client_cannot_send_provenance(client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    for changes in (
        {"card_fields": {"first_name": {"source": "card"}}},
        {"card_reading": {}},
        {"national_id_check": {"mrz": "1"}},
    ):
        assert patch(client, headers, draft_id, changes).status_code == 422


def test_value_typed_before_this_feature_counts_as_typed(client, db, owner) -> None:
    # A draft from before 006 has values but no marks; a reading must not replace them.
    _, headers = owner
    draft_id = new_draft(client, headers)
    patch(client, headers, draft_id, {"first_name": "قديم"})
    db.execute(text("UPDATE drafts SET card_fields = '{}'::jsonb WHERE id = :id"), {"id": draft_id})
    db.commit()
    upload(client, headers, draft_id, "front", "clear_front")
    upload(client, headers, draft_id, "back", "clear_back")
    assert get(client, headers, draft_id)["first_name"] == "قديم"


def test_apply_without_finished_readings_does_nothing(client, db, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    upload(client, headers, draft_id, "front", "clear_front")
    assert card_reading_service.apply_pair(db, uuid.UUID(draft_id)) is False
    card_reading_service.run(uuid.UUID(draft_id), session=db, reader=FakeCardReader())
    assert get(client, headers, draft_id)["first_name"] is None


# --- US7: back fields typed or corrected (owner change) -----------------------------------------


def test_typed_back_fields_are_saved_and_validated(client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    body = patch(
        client,
        headers,
        draft_id,
        {
            "birth_date": "1990-12-29",
            "birth_place": " تكريت - صلاح الدين ",
            "issue_date": "2023-06-15",
            "expiry_date": "2033-06-14",
            "issuing_authority": "مديرية الجنسية والمعلومات المدنية",
        },
    ).json()
    assert body["birth_place"] == "تكريت-صلاح الدين"
    assert body["expiry_date"] == "2033-06-14"
    assert patch(client, headers, draft_id, {"birth_place": "Tikrit"}).json()["code"] == (
        "invalid_place_text"
    )
    assert patch(client, headers, draft_id, {"birth_date": "2023-02-30"}).status_code == 422
    assert patch(client, headers, draft_id, {"issuing_authority": "م" * 101}).json()["code"] == (
        "too_long"
    )


def test_corrected_date_is_kept_on_a_new_reading(client, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers)
    body = patch(client, headers, draft_id, {"issue_date": "2020-01-03"}).json()
    assert body["card_fields"]["issue_date"]["source"] == "edited"
    assert body["card_fields"]["issue_date"]["original"] == "2020-01-02"
    upload(client, headers, draft_id, "back", "clear_back")
    body = get(client, headers, draft_id)
    assert body["issue_date"] == "2020-01-03"
    assert body["card_fields"]["issue_date"]["source"] == "edited"


# --- US4: national ID against the verified MRZ (FR-011–FR-013, research R7) --------------------

NID = "199912345678"
NID_OTHER = "199912345679"


def missing_fields(body: dict) -> set[str]:
    return {m["field"] for m in body["missing"]}


def test_equal_national_ids_raise_nothing(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers))
    assert body["national_id_check"] == {"mrz": NID, "mismatch": False, "confirmed": False}
    assert "national_id_unconfirmed" not in missing_fields(body)


def test_mismatch_must_be_confirmed(client, owner) -> None:
    _, headers = owner
    draft_id = read_card(client, headers, back="back_nid_mismatch")
    body = get(client, headers, draft_id)
    assert body["national_id"] == NID  # the front value is filled
    assert body["national_id_check"] == {"mrz": NID_OTHER, "mismatch": True, "confirmed": False}
    assert "national_id_unconfirmed" in missing_fields(body)

    body = patch(
        client, headers, draft_id, {"national_id": NID, "national_id_confirmed": True}
    ).json()
    assert body["national_id_check"]["confirmed"] is True
    assert "national_id_unconfirmed" not in missing_fields(body)

    # Editing the number drops the confirmation; the comparison runs on the new value.
    body = patch(client, headers, draft_id, {"national_id": "199912345670"}).json()
    assert body["national_id_check"] == {"mrz": NID_OTHER, "mismatch": True, "confirmed": False}
    assert "national_id_unconfirmed" in missing_fields(body)

    # Adopting the MRZ number ends the mismatch.
    body = patch(client, headers, draft_id, {"national_id": NID_OTHER}).json()
    assert body["national_id_check"]["mismatch"] is False
    assert "national_id_unconfirmed" not in missing_fields(body)


def test_confirmation_without_a_mismatch_is_harmless(client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    body = patch(
        client, headers, draft_id, {"national_id": NID, "national_id_confirmed": True}
    ).json()
    assert body["national_id_check"] is None


def test_unverified_mrz_is_never_compared(client, owner) -> None:
    _, headers = owner
    body = get(client, headers, read_card(client, headers, back="back_unverified"))
    assert body["national_id_check"] is None
    assert "national_id_unconfirmed" not in missing_fields(body)


def test_typed_value_is_compared_too(client, owner) -> None:
    _, headers = owner
    draft_id = new_draft(client, headers)
    patch(client, headers, draft_id, {"national_id": NID_OTHER})
    upload(client, headers, draft_id, "front", "clear_front")
    upload(client, headers, draft_id, "back", "clear_back")
    body = get(client, headers, draft_id)
    assert body["national_id"] == NID_OTHER  # typed first: not overwritten
    assert body["national_id_check"]["mismatch"] is True
    assert "national_id_unconfirmed" in missing_fields(body)
