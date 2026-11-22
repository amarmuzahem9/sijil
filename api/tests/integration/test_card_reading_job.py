"""Foundation of feature 006: the fake reader and the reading job (specs/006 research R5, R10).

Synthetic images only (tests/helpers/card_images.py). The job runs synchronously on the test
session. The upload route is wired to the job in US1 (tasks T022); here the service is called
directly.
"""

import io
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from app.config import get_settings
from app.core.timeutil import utc_now
from app.models import CardReading, Draft, ImageAccessLog
from app.services import card_reading_service
from app.services.card_reader import FakeCardReader, ReaderError
from tests.conftest import auth_header, login
from tests.helpers.card_images import scenario_jpeg


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


def _draft_with_images(client, db, headers, front: str, back: str) -> Draft:
    draft_id = str(uuid.uuid4())
    assert (
        client.put(f"/api/drafts/{draft_id}", json={"changes": {}}, headers=headers).status_code
        == 201
    )
    for side, scenario in (("front", front), ("back", back)):
        res = client.post(
            f"/api/drafts/{draft_id}/images/{side}",
            files={"file": (f"{side}.jpg", scenario_jpeg(scenario), "image/jpeg")},
            headers=headers,
        )
        assert res.status_code == 200, res.text
    draft = db.get(Draft, uuid.UUID(draft_id))
    db.refresh(draft)
    client_id = uuid.UUID(headers["X-Client-Id"])
    for image in draft.images:
        card_reading_service.mark_pending(draft, image.side, image.file_name, client_id)
    db.commit()
    return draft


def _readings(db, draft) -> dict[str, CardReading]:
    rows = db.scalars(select(CardReading).where(CardReading.draft_id == draft.id)).all()
    for row in rows:
        db.refresh(row)
    return {row.side: row for row in rows}


# --- fake reader --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario", ["clear_front", "clear_back", "no_card", "two_cards", "reader_failure"]
)
def test_fake_reader_recognises_its_scenarios_after_resize_and_recompression(scenario) -> None:
    original = Image.open(io.BytesIO(scenario_jpeg(scenario)))
    smaller = original.resize((800, 506))
    buf = io.BytesIO()
    smaller.save(buf, format="JPEG", quality=60)
    assert FakeCardReader().scenario_for(buf.getvalue(), "front") == scenario


def test_fake_reader_reads_an_unknown_photo_as_the_clear_card_of_its_slot() -> None:
    image = Image.new("RGB", (800, 500), (235, 230, 220))
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    reader = FakeCardReader()
    assert reader.scenario_for(buf.getvalue(), "front") == "clear_front"
    assert reader.scenario_for(buf.getvalue(), "back") == "clear_back"
    assert reader.scenario_for(b"not an image", "back") == "clear_back"


def test_fake_reader_failure_scenario_raises() -> None:
    with pytest.raises(ReaderError) as info:
        FakeCardReader().read(scenario_jpeg("reader_failure"), "front")
    assert info.value.reason == "unavailable"


# --- the job ------------------------------------------------------------------------------------


def test_job_reads_both_sides_and_logs_the_access(client, db, owner) -> None:
    user, headers = owner
    draft = _draft_with_images(client, db, headers, "clear_front", "clear_back")
    assert card_reading_service.ready_to_read(draft)

    card_reading_service.run(draft.id, session=db, reader=FakeCardReader())

    readings = _readings(db, draft)
    assert {side: r.state for side, r in readings.items()} == {"front": "done", "back": "done"}
    assert readings["front"].result["fields"]["name"]["text"] == "مشترك"
    assert readings["back"].result["mrz"]["verified"] is True
    assert readings["front"].raw["detections"]
    assert readings["front"].finished_at is not None
    logged = db.scalars(select(ImageAccessLog).where(ImageAccessLog.draft_id == draft.id)).all()
    assert sorted((row.side, row.purpose, row.user_id) for row in logged) == [
        ("back", "ocr", user.id),
        ("front", "ocr", user.id),
    ]


def test_job_records_reshoot_and_failure(client, db, owner) -> None:
    _, headers = owner
    draft = _draft_with_images(client, db, headers, "two_cards", "reader_failure")
    card_reading_service.run(draft.id, session=db, reader=FakeCardReader())
    readings = _readings(db, draft)
    assert (readings["front"].state, readings["front"].reason) == ("reshoot", "multiple")
    assert (readings["back"].state, readings["back"].reason) == ("failed", "unavailable")
    assert readings["back"].raw is None


def test_job_does_nothing_with_one_image(client, db, owner) -> None:
    _, headers = owner
    draft_id = str(uuid.uuid4())
    client.put(f"/api/drafts/{draft_id}", json={"changes": {}}, headers=headers)
    client.post(
        f"/api/drafts/{draft_id}/images/front",
        files={"file": ("f.jpg", scenario_jpeg("clear_front"), "image/jpeg")},
        headers=headers,
    )
    draft = db.get(Draft, uuid.UUID(draft_id))
    db.refresh(draft)
    card_reading_service.mark_pending(draft, "front", draft.images[0].file_name, None)
    db.commit()
    assert not card_reading_service.ready_to_read(draft)
    card_reading_service.run(draft.id, session=db, reader=FakeCardReader())
    assert _readings(db, draft)["front"].state == "pending"


def test_result_for_a_replaced_image_is_dropped(client, db, owner) -> None:
    _, headers = owner
    draft = _draft_with_images(client, db, headers, "clear_front", "clear_back")

    class ReplacingReader(FakeCardReader):
        def read(self, image: bytes, side: str):
            if side == "front":  # the marketer replaces the front while it is being read
                reading = db.scalars(
                    select(CardReading).where(
                        CardReading.draft_id == draft.id, CardReading.side == "front"
                    )
                ).one()
                reading.image_file_name = "0" * 32 + ".jpg"
                reading.state = "pending"
                db.commit()
            return super().read(image, side)

    card_reading_service.run(draft.id, session=db, reader=ReplacingReader())
    readings = _readings(db, draft)
    assert readings["front"].state == "pending" and readings["front"].raw is None
    assert readings["back"].state == "done"


def test_timeout_limit(client, db, owner) -> None:
    _, headers = owner
    draft = _draft_with_images(client, db, headers, "clear_front", "clear_back")
    card_reading_service.run(draft.id, session=db, reader=FakeCardReader(), limit_s=-1)
    readings = _readings(db, draft)
    assert {r.reason for r in readings.values()} == {"timeout"}
    assert {r.state for r in readings.values()} == {"failed"}


def test_sweep_marks_stuck_readings_but_not_a_side_waiting_for_its_pair(client, db, owner) -> None:
    _, headers = owner
    draft = _draft_with_images(client, db, headers, "clear_front", "clear_back")
    readings = _readings(db, draft)
    readings["front"].state = "running"
    readings["front"].started_at = utc_now() - timedelta(seconds=120)
    readings["back"].updated_at = utc_now() - timedelta(seconds=120)  # pending, lost job
    db.commit()

    lone_id = str(uuid.uuid4())
    client.put(f"/api/drafts/{lone_id}", json={"changes": {}}, headers=headers)
    client.post(
        f"/api/drafts/{lone_id}/images/front",
        files={"file": ("f.jpg", scenario_jpeg("clear_front"), "image/jpeg")},
        headers=headers,
    )
    lone = db.get(Draft, uuid.UUID(lone_id))
    db.refresh(lone)
    waiting = card_reading_service.mark_pending(lone, "front", lone.images[0].file_name, None)
    db.commit()
    waiting.updated_at = utc_now() - timedelta(seconds=120)
    db.commit()

    assert card_reading_service.sweep_stale(db) == 2
    readings = _readings(db, draft)
    assert {(r.state, r.reason) for r in readings.values()} == {("failed", "timeout")}
    db.refresh(waiting)
    assert waiting.state == "pending"


def test_reading_rows_go_with_the_draft(client, db, owner) -> None:
    _, headers = owner
    draft = _draft_with_images(client, db, headers, "clear_front", "clear_back")
    draft_id = draft.id
    assert client.delete(f"/api/drafts/{draft_id}", headers=headers).status_code == 204
    db.expire_all()
    assert db.scalars(select(CardReading).where(CardReading.draft_id == draft_id)).all() == []
