"""Database and images from one moment (specs/016 research R4, T016).

Pass 1 stores the files present; the database is dumped from one exported snapshot; pass 2
stores the files referenced at that moment but uploaded meanwhile. The app unlinks files only
after its commit, so the only possible gap is a file created and deleted inside the window.
"""

import uuid

import pytest
from sqlalchemy import delete

from app.backup.snapshot import SnapshotConfig, SnapshotFailed, take_snapshot, take_with_retry
from app.core.timeutil import utc_now
from app.models import Request, RequestImage
from tests.helpers.backup import new_image_name, seed
from tests.helpers.card_images import scenario_jpeg


def _cfg(env) -> SnapshotConfig:
    return SnapshotConfig(
        store=env.store,
        uploads=env.uploads,
        recipient=env.key.recipient,
        database_url=env.url,
        app_commit="testcommit",
    )


def _add_image_row(env, name: str) -> None:
    """A new upload: file first, then the committed row (as draft_service does)."""
    (env.uploads / name).write_bytes(scenario_jpeg("clear_front", 80, 50))
    with env.sessions() as s:
        request = s.query(Request).order_by(Request.id).first()
        s.execute(delete(RequestImage).where(RequestImage.request_id == request.id))
        s.add(
            RequestImage(
                id=uuid.uuid4(),
                request_id=request.id,
                side="front",
                file_name=name,
                size_bytes=10,
                width=80,
                height=50,
                uploaded_by=request.marketer_id,
                created_at=utc_now(),
            )
        )
        s.commit()


def _erase_image_row(env, name: str) -> None:
    """An erasure (specs/011): the row goes in a commit, then the file is unlinked."""
    with env.sessions() as s:
        s.execute(delete(RequestImage).where(RequestImage.file_name == name))
        s.commit()
    (env.uploads / name).unlink()


def test_upload_between_pass1_and_snapshot_is_stored_by_pass2(backup_env) -> None:
    env = backup_env
    seed(env)
    late = new_image_name()
    manifest = take_snapshot(
        _cfg(env), "nightly", hooks={"after_pass1": lambda: _add_image_row(env, late)}
    )
    assert late in manifest.image_names
    assert env.store.image_entry(late) is not None
    assert manifest.missing_referenced == 0


def test_referenced_file_gone_before_pass2_fails_then_retry_succeeds(backup_env) -> None:
    env = backup_env
    seed(env)
    late = new_image_name()
    calls = []

    def after_pass1() -> None:
        if not calls:
            _add_image_row(env, late)

    def after_snapshot() -> None:
        if not calls:
            calls.append(1)
            _erase_image_row(env, late)  # created and deleted inside the window

    with pytest.raises(SnapshotFailed) as info:
        take_snapshot(
            _cfg(env),
            "nightly",
            hooks={"after_pass1": after_pass1, "after_snapshot": after_snapshot},
        )
    assert info.value.code == "missing_images"
    assert env.store.list_snapshots(complete_only=False) == []  # the failed folder is removed

    calls.clear()
    attempts: list[str] = []
    manifest = take_with_retry(
        _cfg(env),
        "nightly",
        hooks={"after_pass1": after_pass1, "after_snapshot": after_snapshot},
        on_attempt_failed=attempts.append,
    )
    assert attempts == ["missing_images"]  # first attempt failed, retried once
    assert late not in manifest.image_names
    assert manifest.missing_referenced == 0


def test_retry_happens_only_once(backup_env) -> None:
    env = backup_env
    seed(env)
    late = [new_image_name()]

    def after_pass1() -> None:
        late[0] = new_image_name()
        _add_image_row(env, late[0])

    def after_snapshot() -> None:
        (env.uploads / late[0]).unlink()  # the row stays: a real broken state

    attempts: list[str] = []
    with pytest.raises(SnapshotFailed) as info:
        take_with_retry(
            _cfg(env),
            "nightly",
            hooks={"after_pass1": after_pass1, "after_snapshot": after_snapshot},
            on_attempt_failed=attempts.append,
        )
    assert info.value.code == "missing_images"
    assert attempts == ["missing_images"]


def test_erasure_committed_before_the_snapshot_is_not_required(backup_env) -> None:
    env = backup_env
    seeded = seed(env)
    gone = sorted(seeded.request_image_names)[0]
    _erase_image_row(env, gone)
    manifest = take_snapshot(_cfg(env), "nightly")
    assert gone not in manifest.image_names
    assert manifest.missing_referenced == 0
