"""The drill's comparison after a restore (specs/016 FR-015, research R9, T032)."""

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from app.backup import restore
from app.backup.snapshot import SnapshotConfig, take_snapshot
from app.models import SasSubscriber
from tests.helpers.backup import new_image_name, seed

AT = datetime(2026, 11, 27, 10, 0, tzinfo=UTC)


@pytest.fixture
def restored(backup_env):
    """A snapshot, and a "restored" copy: the same database and a staged uploads folder."""
    env = backup_env
    seed(env)
    manifest = take_snapshot(
        SnapshotConfig(
            store=env.store,
            uploads=env.uploads,
            recipient=env.key.recipient,
            database_url=env.url,
            app_commit="testcommit",
        ),
        "nightly",
    )
    staged = env.tmp / "staged"
    staged.mkdir()
    restore.stage_images(env.store, manifest, env.key.identity, staged)
    return env, manifest, staged


def test_faithful_restore_passes(restored) -> None:
    env, manifest, staged = restored
    result = restore.verify_restored(env.url, staged, manifest)
    assert result.passed is True and result.reason is None
    assert result.compared["requests"] == {"expected": 2, "found": 2}
    assert result.compared["images"] == {"expected": 6, "found": 6}
    assert result.compared["missing_referenced"] == 0


def test_count_difference_fails(restored) -> None:
    env, manifest, staged = restored
    with env.sessions() as s:
        s.execute(delete(SasSubscriber))
        s.commit()
    result = restore.verify_restored(env.url, staged, manifest)
    assert result.passed is False
    assert result.reason == "count_mismatch"
    assert result.compared["sas_subscribers"] == {"expected": 1, "found": 0}


def test_missing_image_fails(restored) -> None:
    env, manifest, staged = restored
    (staged / manifest.images[0].name).unlink()
    result = restore.verify_restored(env.url, staged, manifest)
    assert (result.passed, result.reason) == (False, "images_missing")


def test_changed_image_fails(restored) -> None:
    env, manifest, staged = restored
    (staged / manifest.images[0].name).write_bytes(b"\xff\xd8\xff not the same")
    result = restore.verify_restored(env.url, staged, manifest)
    assert (result.passed, result.reason) == (False, "image_hash_mismatch")


def test_referenced_but_missing_fails(restored) -> None:
    env, manifest, staged = restored
    # A row pointing at a file that is in neither the manifest nor the folder.
    import uuid

    from app.core.timeutil import utc_now
    from app.models import Request, RequestImage

    with env.sessions() as s:
        request = s.query(Request).first()
        s.query(RequestImage).filter_by(request_id=request.id, side="front").delete()
        s.add(
            RequestImage(
                id=uuid.uuid4(),
                request_id=request.id,
                side="front",
                file_name=new_image_name(),
                size_bytes=1,
                width=1,
                height=1,
                uploaded_by=request.marketer_id,
                created_at=utc_now(),
            )
        )
        s.commit()
    result = restore.verify_restored(env.url, staged, manifest)
    assert result.passed is False
    assert result.compared["missing_referenced"] == 1


def test_drill_record_holds_counts_only(restored) -> None:
    env, manifest, staged = restored
    result = restore.verify_restored(env.url, staged, manifest)
    name = restore.record_drill(env.store, manifest.id, result, at=AT, source="server")
    assert name.endswith("-drill.json")
    data = json.loads((env.store.history / name).read_text())
    assert data["result"] == "passed"
    assert data["snapshot_id"] == manifest.id
    assert data["details"]["source"] == "server"
    text = json.dumps(data, ensure_ascii=False)
    for personal in ("تجربة", "0790000", "حي تجريبي"):
        assert personal not in text
    failed = restore.DrillResult(passed=False, reason="count_mismatch", compared={})
    name2 = restore.record_drill(env.store, manifest.id, failed, at=AT, source="external")
    assert json.loads((env.store.history / name2).read_text())["result"] == "failed"
