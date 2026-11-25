# Research: Deployment and Backups (016)

All spec questions were answered (spec «Clarifications», `docs/system.md` 1.21 §15). The decisions below cover the
technical unknowns.

## R1 — Where backups run: a separate `backup` service, no Docker socket

**Decision**: A new compose service `backup`, built from the **same image as `api`** (the api image gains
`postgresql-client-16` and `age`), started with a different command (`python -m app.backup serve`). It mounts:
the database network, `uploads` **read-only**, and the backup directory (`BACKUP_DIR` on the server, a named volume
locally). `api` and `web` never mount the backup directory. The container has no Docker socket. Operator actions that
need Docker (restore, drill, weekly copy, deploy) are host scripts in `scripts/` that call
`docker compose run --rm backup …` with the extra mounts they need.

**Rationale**: FR-010 (backups readable only by the server administrator, never by the app containers); one image
means the backup code shares the models, settings and migrations with the app (restore can check the Alembic
revision, R7) and the tests run in the existing `api` test container.

**Alternatives**: host cron + shell scripts (no access to the models, schedule invisible to the app, harder to test);
backup code inside `api` (the app container would then read the backups and hold the image volume read-write for
restore); restic/borg (R3).

## R2 — Encryption without a passphrase on the server: `age` with a passphrase-protected identity

**Decision**: `age` (X25519). Set-up, once, interactive (`scripts/backup.sh init-key`): generate an identity, encrypt
it with a passphrase (`age -p`, which offers a generated 10-word passphrase), save it as `key.age` in the backup
directory and on the external drive, and print the public recipient (`age1…`), which goes into `.env` as
`BACKUP_AGE_RECIPIENT`. The recipient is public: the server can **encrypt** every backup unattended but cannot
**decrypt** any (FR-010a). Decrypting (restore, drill) asks for the passphrase on the terminal; the decrypted identity
lives only in memory/tmpfs of the one-off container. Every file in a backup is an age file except the plaintext
manifest (R4), which holds no personal data.

**Rationale**: Owner decision Q1-A. The passphrase is never on the server, in `.env`, in git or in a backup;
`key.age` is useless without it. `age` is a single, widely packaged tool, so a backup can also be opened by hand on
any machine (documented in `deploy/backup.md`).

**Alternatives**: symmetric encryption (restic/borg/gpg -c) needs the passphrase at backup time → it would live on
the server; GPG public keys (heavier, key-ring handling); `pyrage` (no CLI for manual recovery).

## R3 — Image deduplication: encrypted, write-once image objects shared by snapshots

**Decision**: Backup directory layout:

```text
BACKUP_DIR/
├── key.age                      # passphrase-protected identity (R2)
├── images/<uuid hex>.jpg.age    # one encrypted object per stored image, written once
├── snapshots/<YYYYMMDD-HHMMSS>-<kind>/
│   ├── db.dump.age              # pg_dump -Fc, encrypted
│   ├── manifest.json            # plaintext, no personal data (R4)
│   └── DONE                     # written last; a snapshot without it is incomplete
└── history/<time>-<type>.json   # drills, external copies, restores, deploys (R8)
```

An image object is written only if absent (stored names are random `<uuid4 hex>.jpg`, never changed, R6 of 005). Each
snapshot's manifest lists the image objects it needs, so each snapshot restores on its own. Retention removes
snapshots, then garbage-collects image objects referenced by no kept snapshot.

**Rationale**: FR-004 / SC-006: with ~1 GB of images, 30 snapshots cost ~1 GB of images + 30 small dumps instead of
30 GB. Restic/borg would deduplicate too but need the symmetric key at backup time (R2).

**Alternatives**: a full tar per night (30× the images, does not fit 14 GB); hard-link snapshots (`rsync
--link-dest`) of plaintext files (unencrypted).

## R4 — One consistent moment for database and images

**Decision**: Three steps per backup:
1. **Pass 1**: list `uploads`, encrypt every file without an object yet (the slow part; the app keeps running).
2. **Snapshot**: open a `REPEATABLE READ READ ONLY` transaction, `pg_export_snapshot()`, run
   `pg_dump --snapshot=…` (piped into `age`), and in the same transaction read the referenced file names
   (`draft_images`, `request_images`, `legacy_images`, `card_readings.image_file_name`), the Alembic revision and the
   summary counts.
3. **Pass 2**: encrypt any referenced file still without an object (uploaded during pass 1/2).

The app unlinks image files only **after** its commit (011 erasure, draft image replace/delete, `prune-uploads`), so
any file referenced at the snapshot moment either was stored in pass 1 or still exists in pass 2. The only failure is
a file created and deleted inside the backup window: then `missing_referenced > 0`, the backup is marked failed
(`missing_images`) and retried once at once.

`manifest.json`: snapshot id, kind, started/finished (UTC), app version (git commit), Alembic revision, counts
(requests, drafts, legacy subscribers, SAS subscribers, users, audit entries), list of `{name, size, sha256_plain,
sha256_enc}` for each image, `sha256` + size of `db.dump.age`. File names are random and carry no personal data; the
counts are aggregates.

**Rationale**: FR-001, acceptance US1-2, SC-004 (no lock on the app; `pg_dump` does not block writers).

## R5 — Schedule, requests from the app, single operation

**Decision**: `backup serve` is a loop (restart `unless-stopped`): every 15 s it (a) writes a heartbeat and the free
disk space into `backup_status`, (b) starts a requested manual backup if any, (c) starts the nightly backup when the
Baghdad clock passes `BACKUP_NIGHTLY_AT` (default `03:00`) and no nightly snapshot exists for that Baghdad day
(catches up after a restart), (d) re-syncs the database mirror from the files (R8). One operation at a time: a
PostgreSQL session advisory lock `BACKUP_LOCK = 160_016`, taken by `serve` and by every one-off command; a second
operation refuses with `backup_busy`. The manual button inserts a `backup_runs` row `requested`; a partial unique
index allows only one row in `requested|running`.

**Rationale**: FR-005, FR-008; the schedule survives restarts and deploys (the service is part of the stack); no cron
on the host to forget.

## R6 — Retention and disk guard

**Decision**: After each successful backup: remove snapshot folders older than 30 days by start time (all kinds),
never the newest successful one; remove incomplete folders (no `DONE`) older than 1 day; then garbage-collect image
objects. A failed snapshot never triggers removal. Before a backup: estimate = size of not-yet-stored images + last
dump size; refuse (`disk_low`) if free space after it would be under `BACKUP_MIN_FREE_GB` (default 2). The same margin
drives the warning (FR-017).

## R7 — Restore: verify, stage, swap

**Decision**: `scripts/restore.sh [snapshot-id] [--from-external]`:
1. Show the snapshot (time Baghdad, counts, app version), warn that everything after it is lost, including «حذف مشترك»
   erasures; confirm by typing the snapshot date.
2. Refuse if the snapshot's Alembic revision is not in this code's migration history (a backup from a newer version).
   An older revision is fine: `api` runs `alembic upgrade head` at start.
3. Take a `pre_restore` backup of the current state (no passphrase needed).
4. Ask the passphrase; verify `sha256_enc` of every file, decrypt the images into a temporary volume and check
   `sha256_plain`. Any mismatch → stop, nothing changed.
5. Stop `api` and `backup` (users get «الخدمة غير متاحة مؤقتاً» from `web`); recreate the database and `pg_restore`;
   replace the contents of `uploads` with the temporary volume (owner 10001); remove the temporary volume.
6. Start the stack, wait for health, write the `restore` history file and an audit line (`backup.restore`, actor
   none, snapshot id only).

`--from-external` reads the snapshot from the mounted external drive (same layout). Restore on a new server: install
per `deploy/backup.md`, write `.env` by hand, mount the drive, run restore.

**Rationale**: FR-012–FR-014; the live data is touched only after the backup has been fully verified.

## R8 — The database mirrors the files

**Decision**: The backup files are the source of truth. The tables `backup_runs`, `backup_events` and `backup_status`
are a mirror for the admin page: `serve` upserts them from `snapshots/*/manifest.json` and `history/*.json` on every
loop. After a restore (the database goes back to the past) the mirror is rebuilt within 15 s, so the page shows the
real list, including the restore itself.

**Rationale**: Otherwise restoring a backup would erase the record of every later backup and of the restore.

## R9 — Restore drill: an isolated throwaway stack

**Decision**: `scripts/backup.sh drill [snapshot-id]` (also called at the end of `weekly`). It starts a separate compose
project `sijil-drill` (`docker-compose.drill.yml`): `db` (tmpfs data), `api` (the live image), and a one-off
restorer, all on one `internal: true` network (no internet, no published port, no shared volume with the live stack).
It writes a throwaway env file in tmpfs (random secrets, `APP_ENV=staging`, real modes, no OTPIQ key). It restores
the snapshot as in R7 steps 2 and 4–5, waits for `api` health (migrations ran), then runs `python -m app.backup
verify-restored` inside the drill: counts equal the manifest, every manifest image exists with the right
`sha256_plain`, referenced-but-missing = 0. It records the result (`history/…-drill.json`: snapshot, passed/failed,
counts compared, reason) and runs `down -v`. Nothing is sent: no internet, OTPIQ key empty.

**Rationale**: FR-015; the project rule for real card images (container without network, no results kept beyond the
pass/fail counts). Unattended nightly checking without the passphrase: `sha256_enc` of the dump and new objects is
re-read after writing (FR-015a).

## R10 — Weekly external copy

**Decision**: `scripts/backup.sh weekly`: the operator plugs the drive in and mounts it at `BACKUP_EXTERNAL_DIR`
(from `.env`). The script refuses unless that path is a mount point (`mountpoint -q`) holding the marker file
`.sijil-external` (created once by `backup.sh init-external`), so it never writes onto the server's own disk by
mistake. It copies the latest successful snapshot and its missing image objects plus `key.age` into the same layout
on the drive (objects already there are reused, nothing on the drive is removed or overwritten), checks free space
first, re-reads and verifies `sha256_enc` of every copied file, records `history/…-external.json`, then runs the drill
on the copy (asks the passphrase), syncs, and prints «يمكن فصل الهارد الآن».

**Rationale**: Owner decisions Q2-B and Q3-A; FR-007. Deduplication on the drive too keeps its growth to new images +
one dump a week.

## R11 — Deploy: one script, two modes

**Decision**: `scripts/deploy.sh` (staging and production by `APP_ENV`); `scripts/deploy-staging.sh` stays as a
one-line wrapper. The server overlay `docker-compose.staging.yml` is renamed `docker-compose.server.yml` (same content
plus the `backup` bind mount); docs and the `sijil` alias change. Steps:
1. Today's pre-flight checks, plus: `APP_ENV` ∈ {staging, production}; `BACKUP_DIR` exists, owned by uid 10001,
   mode 700; `BACKUP_AGE_RECIPIENT` set and `key.age` present; in production `OCR_MODE`, `OTP_MODE`, `DRIVE_MODE` not
   `fake` and `OTP_FAKE_CODE` empty; in production refuse while demo accounts are active (run `go-live` first).
2. If the stack is running: `backup now --kind pre_deploy` (stop on failure). First install: skipped, said so.
3. Remember the current commit; `git pull --ff-only`; `up -d --build --remove-orphans --wait` (includes `backup`).
4. Health inside and through the public URL (as today). `seed-demo` only in staging.
5. Record `history/…-deploy.json` (old/new commit, mode, result, pre-deploy snapshot). On failure print the
   pre-deploy snapshot and the rollback steps (`git checkout <old>`, `deploy.sh`, and `restore.sh <snapshot>` only if
   the new version changed the data).

`python -m app.cli go-live`: deactivates the demo accounts (never deletes), audited `system.go_live`; run once by the
operator before switching `.env` to `APP_ENV=production`.

## R12 — Warnings to the main admin

**Decision**: `GET /api/admin/home` adds `backup_warnings: [code]` for the main admin only. Codes: `last_failed`,
`no_recent_backup` (no success in 36 h), `external_overdue` (no external copy in 8 days), `drill_failed_or_overdue`,
`disk_low`, `service_down` (heartbeat older than 10 min — reaches SC-005 well within one hour). Computed from the
mirror tables; no subscriber data.

## R13 — Testing

**Decision**: pytest (in the `api` container, which now has `pg_dump` and `age`) for manifest/reference collection,
missing-image detection, deduplication, retention selection, disk guard, mirror sync, lock, manual-request API and
permissions, warnings, `go-live`; each test red first. A shell end-to-end `scripts/backup-e2e.sh` runs on a throwaway
compose project with synthetic data and a throwaway key: backup → change data → restore → compare; drill pass; drill
on a corrupted object fails; weekly copy to a temp "drive" with and without the marker; deploy pre-flight refusals.
Vitest for the backup page and the home warning; one Playwright case (page + manual button).
