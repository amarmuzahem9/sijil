"""`python -m app.backup <command>` (specs/016 contracts/cli.md).

serve                         the `backup` service loop
now [--kind manual|pre_deploy|pre_restore]   one backup now
list                          the snapshots on this server
init-key [--passphrase-stdin] create key.age once and print BACKUP_AGE_RECIPIENT
latest | show SID | check SID | files SID      read a snapshot (no passphrase needed)
restore-into SID --staging D --uploads D [--passphrase-stdin]   restore (database + images)
verify-restored SID --uploads D               the drill's comparison (JSON on stdout)
record drill|restore SID                      write a drill/restore record (+ audit)
status                                        last backup, copy, drill and the warnings

Exit codes: 0 ok, 3 busy, 4 disk_low, 6 drill failed, 7 restore refused, 1 other.
Output carries ids, times, sizes and
counts only, never personal data or keys.
"""

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from app.backup import keyfile, restore
from app.backup.errors import BackupBusy, SnapshotFailed
from app.backup.restore import RestoreRefused
from app.backup.retention import read_manifest
from app.backup.serve import BackupService
from app.backup.store import BackupStore
from app.core.timeutil import BAGHDAD, utc_now

EXIT_BUSY = 3
EXIT_DISK_LOW = 4
EXIT_DRILL_FAILED = 6
EXIT_REFUSED = 7


def _list(service: BackupService) -> int:
    for sid in service.store.list_snapshots():
        m = read_manifest(service.store, sid)
        local = m.started_at.astimezone(BAGHDAD)
        print(
            f"{sid}  {local:%Y-%m-%d %H:%M} بغداد  {m.kind:<11}  "
            f"{m.total_size / 1024 / 1024:8.1f} MB  طلبات={m.counts.requests}  "
            f"قدامى={m.counts.legacy_subscribers}  SAS={m.counts.sas_subscribers}  "
            f"صور={len(m.images)}"
        )
    return 0


def _now(service: BackupService, kind: str) -> int:
    try:
        row = service.run(kind)
    except BackupBusy:
        print("يوجد نسخ جارٍ الآن (busy)", file=sys.stderr)
        return EXIT_BUSY
    except SnapshotFailed as exc:
        print(f"فشل النسخ: {exc.code}", file=sys.stderr)
        return EXIT_DISK_LOW if exc.code == "disk_low" else 1
    print(f"تم النسخ: {row.snapshot_id}  ({row.total_size} bytes, {row.image_count} صورة)")
    return 0


def _init_key(from_stdin: bool) -> int:
    from app.config import get_settings

    store = BackupStore(get_settings().backup_dir)
    store.ensure_layout()
    key_path = store.key_path
    passphrase = sys.stdin.readline().rstrip("\n") if from_stdin else None
    try:
        recipient = keyfile.create(key_path, passphrase=passphrase)
    except keyfile.KeyfileError as exc:
        print(f"تعذّر إنشاء المفتاح: {exc}", file=sys.stderr)
        return 1
    print("تم إنشاء key.age. ضع هذا السطر في .env (المفتاح العام، ليس سراً):")
    print(f"BACKUP_AGE_RECIPIENT={recipient}")
    print("اكتب كلمة السر واحفظها خارج السيرفر. بدونها لا تُفتح أي نسخة.")
    return 0


def _store(source: str | None) -> BackupStore:
    from app.config import get_settings

    return BackupStore(source or get_settings().backup_dir)


def _refused(exc: RestoreRefused) -> int:
    print(f"رُفض الاسترجاع: {exc.code}", file=sys.stderr)
    return EXIT_REFUSED


def _latest(store: BackupStore) -> int:
    complete = store.list_snapshots()
    if not complete:
        print("لا توجد نسخة", file=sys.stderr)
        return 1
    print(complete[-1])
    return 0


def _show(store: BackupStore, sid: str) -> int:
    try:
        m = restore.verify(store, sid)
    except RestoreRefused as exc:
        return _refused(exc)
    local = m.started_at.astimezone(BAGHDAD)
    c = m.counts
    print(f"النسخة: {m.id}")
    print(f"وقتها: {local:%Y-%m-%d %H:%M} بتوقيت بغداد  (نوعها {m.kind}، إصدار {m.app_commit})")
    print(
        f"فيها: طلبات={c.requests}  مسودات={c.drafts}  قدامى={c.legacy_subscribers}  "
        f"SAS={c.sas_subscribers}  حسابات={c.users}  سجل={c.audit_entries}  صور={len(m.images)}"
    )
    print(f"DATE={local:%Y-%m-%d}")
    return 0


def _check(store: BackupStore, sid: str) -> int:
    try:
        restore.check_revision(restore.verify(store, sid))
    except RestoreRefused as exc:
        return _refused(exc)
    print(f"النسخة سليمة: {sid}")
    return 0


def _files(store: BackupStore, sid: str) -> int:
    try:
        m = restore.verify(store, sid)
    except RestoreRefused as exc:
        return _refused(exc)
    print("key.age")
    for name in ("manifest.json", "db.dump.age", "DONE"):
        print(f"snapshots/{sid}/{name}")
    for entry in m.images:
        print(f"images/{entry.name}.age")
        print(f"images/{entry.name}.age.meta")
    return 0


def _passphrase(from_stdin: bool) -> str | None:
    return sys.stdin.readline().rstrip("\n") if from_stdin else None


def _restore_into(store: BackupStore, args: argparse.Namespace) -> int:
    """Verify, stage the images, recreate the database, then swap the image storage."""
    from app.config import get_settings

    staging, uploads = Path(args.staging), Path(args.uploads)
    try:
        manifest = restore.verify(store, args.sid)
        restore.check_revision(manifest)
        with keyfile.unlocked(store.key_path, passphrase=_passphrase(args.passphrase_stdin)) as idn:
            restore.stage_images(store, manifest, idn, staging)
            restore.restore_database(store, manifest, idn, get_settings().database_url)
        restore.swap_uploads(staging, uploads)
    except RestoreRefused as exc:
        return _refused(exc)
    except keyfile.KeyfileError:
        print("رُفض الاسترجاع: كلمة السر غير صحيحة أو key.age غير موجود", file=sys.stderr)
        return EXIT_REFUSED
    print(f"تم استرجاع {manifest.id}: {len(manifest.images)} صورة")
    return 0


def _verify_restored(store: BackupStore, sid: str, uploads: str) -> int:
    from app.config import get_settings

    try:
        manifest = restore.verify(store, sid)
    except RestoreRefused as exc:
        return _refused(exc)
    result = restore.verify_restored(get_settings().database_url, Path(uploads), manifest)
    print(json.dumps(asdict(result), ensure_ascii=False))
    return 0 if result.passed else EXIT_DRILL_FAILED


def _record(store: BackupStore, args: argparse.Namespace) -> int:
    if args.type == "drill":
        data = json.loads(sys.stdin.read())
        result = restore.DrillResult(
            passed=bool(data["passed"]),
            reason=data.get("reason"),
            compared=data.get("compared", {}),
        )
        restore.record_drill(store, args.sid, result, at=utc_now(), source=args.source_label)
        return 0
    if args.type == "restore":
        from app.db import get_sessionmaker
        from app.services import audit_service

        details = {"pre_restore": args.pre_restore}
        store.write_history(
            "restore",
            {"result": "succeeded", "snapshot_id": args.sid, "details": details},
            at=utc_now(),
        )
        with get_sessionmaker()() as db:
            audit_service.record(
                db,
                actor_id=None,
                action="backup.restore",
                entity_type="backup_run",
                entity_id=args.sid,
                after=details,
            )
            db.commit()
        return 0
    return 2


def _status() -> int:
    """What the backup page shows, for the operator. Exit 1 when there is a warning."""
    from sqlalchemy import select

    from app.db import get_sessionmaker
    from app.models import BackupEvent, BackupRun
    from app.services import backup_warnings

    def local(at) -> str:
        return f"{at.astimezone(BAGHDAD):%Y-%m-%d %H:%M}" if at else "—"

    with get_sessionmaker()() as db:
        last = db.scalar(
            select(BackupRun)
            .where(BackupRun.status.in_(("succeeded", "failed")))
            .order_by(BackupRun.finished_at.desc().nulls_last())
        )
        events = {
            t: db.scalar(
                select(BackupEvent).where(BackupEvent.type == t).order_by(BackupEvent.at.desc())
            )
            for t in ("external_copy", "drill")
        }
        warnings = backup_warnings.compute(db, utc_now())
    if last is None:
        print("آخر نسخة: لا يوجد")
    else:
        state = "ناجحة" if last.status == "succeeded" else f"فشلت ({last.error_code})"
        print(f"آخر نسخة: {last.snapshot_id or last.id}  {local(last.finished_at)}  {state}")
    ext, drill = events["external_copy"], events["drill"]
    print(f"آخر نسخة على الهارد: {local(ext.at) if ext else 'لا يوجد'}")
    if drill is None:
        print("تجربة الاسترجاع: لم تُجرَّب بعد")
    else:
        result = "نجحت" if drill.result == "passed" else "فشلت"
        print(f"تجربة الاسترجاع: {result}  {local(drill.at)}")
    for code in warnings:
        print(f"تحذير: {backup_warnings.TEXTS[code]}")
    return 1 if warnings else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.backup")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    now = sub.add_parser("now")
    now.add_argument("--kind", choices=["manual", "pre_deploy", "pre_restore"], default="manual")
    sub.add_parser("list")
    sub.add_parser("status")
    init = sub.add_parser("init-key")
    init.add_argument("--passphrase-stdin", action="store_true")
    for name in ("latest", "show", "check", "files", "restore-into", "verify-restored", "record"):
        p = sub.add_parser(name)
        p.add_argument("--source", help="backup folder (default BACKUP_DIR)")
        if name == "record":
            p.add_argument("type", choices=["drill", "restore"])
        if name != "latest":
            p.add_argument("sid")
        if name in ("restore-into", "verify-restored"):
            p.add_argument("--uploads", required=True)
        if name == "restore-into":
            p.add_argument("--staging", required=True)
            p.add_argument("--passphrase-stdin", action="store_true")
        if name == "record":
            p.add_argument("--source-label", choices=["server", "external"], default="server")
            p.add_argument("--pre-restore", default=None)
    args = parser.parse_args(argv)
    if args.command == "init-key":
        return _init_key(args.passphrase_stdin)
    if args.command == "status":
        return _status()
    if args.command in ("latest", "show", "check", "files", "restore-into", "verify-restored"):
        store = _store(args.source)
        if args.command == "latest":
            return _latest(store)
        if args.command == "show":
            return _show(store, args.sid)
        if args.command == "check":
            return _check(store, args.sid)
        if args.command == "files":
            return _files(store, args.sid)
        if args.command == "restore-into":
            return _restore_into(store, args)
        return _verify_restored(store, args.sid, args.uploads)
    if args.command == "record":
        return _record(_store(args.source), args)

    service = BackupService.from_settings()
    if args.command == "serve":  # pragma: no cover - long-running
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
        service.serve()
        return 0
    if args.command == "now":
        return _now(service, args.kind)
    return _list(service)


if __name__ == "__main__":
    sys.exit(main())
