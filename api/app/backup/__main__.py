"""`python -m app.backup <command>` (specs/016 contracts/cli.md).

serve                         the `backup` service loop
now [--kind manual|pre_deploy|pre_restore]   one backup now
list                          the snapshots on this server
init-key [--passphrase-stdin] create key.age once and print BACKUP_AGE_RECIPIENT

Exit codes: 0 ok, 3 busy, 4 disk_low, 1 any other failure. Output carries ids, times, sizes and
counts only, never personal data or keys.
"""

import argparse
import logging
import sys

from app.backup import keyfile
from app.backup.errors import BackupBusy, SnapshotFailed
from app.backup.retention import read_manifest
from app.backup.serve import BackupService
from app.backup.store import BackupStore
from app.core.timeutil import BAGHDAD

EXIT_BUSY = 3
EXIT_DISK_LOW = 4


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.backup")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    now = sub.add_parser("now")
    now.add_argument("--kind", choices=["manual", "pre_deploy", "pre_restore"], default="manual")
    sub.add_parser("list")
    init = sub.add_parser("init-key")
    init.add_argument("--passphrase-stdin", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "init-key":
        return _init_key(args.passphrase_stdin)

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
