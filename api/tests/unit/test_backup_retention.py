"""30-day retention and image garbage collection (specs/016 FR-006, research R6, T017)."""

from datetime import UTC, datetime, timedelta

from app.backup import retention
from app.backup.manifest import Counts, DumpEntry, ImageEntry, Manifest
from app.backup.store import BackupStore
from tests.helpers.backup import image_name, make_age_key

NOW = datetime(2026, 12, 31, 12, 0, tzinfo=UTC)


def _id(days_ago: float, kind: str = "nightly") -> str:
    return f"{NOW - timedelta(days=days_ago):%Y%m%d-%H%M%S}-{kind}"


def test_older_than_30_days_selected_of_every_kind() -> None:
    complete = [
        _id(45, "manual"),
        _id(31, "pre_deploy"),
        _id(30.5, "pre_restore"),
        _id(29),
        _id(1),
    ]
    assert retention.select_removals(complete, [], NOW, last_run_succeeded=True) == [
        _id(45, "manual"),
        _id(31, "pre_deploy"),
        _id(30.5, "pre_restore"),
    ]


def test_exactly_30_days_is_kept() -> None:
    assert retention.select_removals([_id(30), _id(1)], [], NOW, last_run_succeeded=True) == []


def test_newest_successful_never_removed_whatever_its_age() -> None:
    complete = [_id(90), _id(60)]
    assert retention.select_removals(complete, [], NOW, last_run_succeeded=True) == [_id(90)]


def test_incomplete_folders_older_than_a_day() -> None:
    incomplete = [_id(3), _id(1.5), _id(0.5)]
    assert retention.select_removals([_id(1)], incomplete, NOW, last_run_succeeded=True) == [
        _id(3),
        _id(1.5),
    ]


def test_nothing_after_a_failed_run() -> None:
    complete = [_id(90), _id(60), _id(1)]
    assert retention.select_removals(complete, [_id(5)], NOW, last_run_succeeded=False) == []


def _manifest(sid: str, names: list[str]) -> Manifest:
    return Manifest(
        id=sid,
        kind=sid.rsplit("-", 1)[1],
        started_at=NOW,
        finished_at=NOW,
        app_commit="c",
        alembic_revision="0019",
        counts=Counts(0, 0, 0, 0, 0, 0),
        dump=DumpEntry(size=1, sha256_enc="a" * 64),
        images=[ImageEntry(n, 1, "b" * 64, "c" * 64) for n in names],
    )


def test_unreferenced_objects() -> None:
    stored = {image_name(1), image_name(2), image_name(3)}
    kept = [_manifest(_id(1), [image_name(1)]), _manifest(_id(2), [image_name(2)])]
    assert retention.unreferenced_objects(stored, kept) == {image_name(3)}


def test_apply_removes_old_snapshots_and_only_unreferenced_objects(tmp_path) -> None:
    key = make_age_key(tmp_path)
    store = BackupStore(tmp_path / "b")
    store.ensure_layout()
    for n in (1, 2, 3):
        src = tmp_path / image_name(n)
        src.write_bytes(bytes([n]) * 10)
        store.put_image(src, key.recipient)
    plan = {_id(40): [image_name(1), image_name(3)], _id(10): [image_name(2), image_name(3)]}
    for sid, names in plan.items():
        folder = store.begin_snapshot(sid)
        store.write_json_atomic(folder / "manifest.json", _manifest(sid, names).to_json())
        store.mark_done(sid)
    stale = store.begin_snapshot(_id(2, "manual"))  # incomplete, older than a day
    assert stale.exists()

    result = retention.apply(store, NOW)

    assert sorted(result.removed_snapshots) == sorted([_id(40), _id(2, "manual")])
    assert store.list_snapshots(complete_only=False) == [_id(10)]
    assert result.removed_objects == [image_name(1)]
    assert not store.image_path(image_name(1)).exists()
    assert not (store.images / f"{image_name(1)}.age.meta").exists()
    assert store.image_path(image_name(2)).exists()
    assert store.image_path(image_name(3)).exists()
