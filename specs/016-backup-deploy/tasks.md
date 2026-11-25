---

description: "Task list for feature 016: Deployment and Backups"
---

# Tasks: Deployment and Backups

**Input**: Design documents from `specs/016-backup-deploy/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [contracts/cli.md](./contracts/cli.md),
[quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's rule: **each new test is run red before its
code is written**. Report red and green for every test task.

**Test rules**:
- Synthetic data only: generated JPEGs (as in the 005/014 tests), made-up names and phones. No real card image or
  subscriber data (CLAUDE.md).
- A throwaway `age` key is generated per test run (`age-keygen` into `tmp_path`), never committed. Test passphrases
  are synthetic.
- **Nothing runs on the real server**: no restore, drill, weekly copy or deploy outside the developer machine (owner
  rule, 2026-11-25). Shell end-to-end runs only on a throwaway compose project (`sijil-bk-e2e`).
- Vitest runs from PowerShell (project note). Host edit scripts write LF (project note).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md
- **Paths**: `api/` (FastAPI + backup package), `web/src/` (React), `scripts/`, `deploy/`, `e2e/tests/`

**Implementation batches** (each one ends at a phase boundary, with a commit):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T014 |
| 2 | 3 (US1 nightly backup, retention, service) | T015–T030 |
| 3 | 4 (US2 restore and drill) | T031–T042 |
| 4 | 5 (US3 page, manual button, warnings) | T043–T054 |
| 5 | 6 (US4 weekly external copy) | T055–T060 |
| 6 | 7 (US5 deploy, go-live) | T061–T069 |
| 7 | 8 (Polish, docs, manual test) | T070–T077 |

---

## Phase 1: Setup

- [x] T001 Confirm the baseline: `docker compose up -d`, `docker compose exec api pytest` and `cd web; npm test`
  (PowerShell) green on the branch before any change. Note the counts in the batch report.
- [x] T002 Add `postgresql-client-16` (PGDG apt repository, signed key) and `age` to `api/Dockerfile` (research R1).
  After rebuilding, `docker compose exec api pg_dump --version` prints 16.x and `age --version` works.
- [x] T003 [P] Add settings to `api/app/config.py`: `backup_dir` (default `/data/backups`), `backup_age_recipient`
  (an age public key when set; empty is allowed by the settings, and enforced instead by `deploy.sh` and the
  `backup` service, so the app still starts before `init-key`), `backup_nightly_at` (`HH:MM`,
  default `03:00`), `backup_min_free_gb` (default 2), `backup_external_dir` (display only). Add the
  variables to `.env.example` with comments (contracts/cli.md «.env additions»).
- [x] T004 [P] Add error codes with Arabic messages to `api/app/errors.py`: `backup_busy` «يوجد نسخ جارٍ الآن»,
  `backup_service_down` «خدمة النسخ متوقفة» (contracts/api.md).

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the mirror tables, the file layout, encryption and the manifest, which every story uses.

### Tests (write first, run red)

- [x] T005 [P] Migration test `api/tests/integration/test_migration_0019.py`:
  - tables `backup_runs`, `backup_events`, `backup_status` exist with the columns of data-model.md;
  - data-model.md `backup_runs.status` and `backup_runs.kind` refuse values outside their lists;
  - data-model.md `backup_runs.error_code` refuses an unknown code and accepts NULL;
  - data-model.md `backup_runs.snapshot_id` is unique and accepts NULL on several rows;
  - the partial unique index allows only one `backup_runs` row with `status IN ('requested','running')`;
  - data-model.md `backup_events.type` and `backup_events.result` refuse values outside their lists;
  - `backup_status` holds at most one row (`id = 1`);
  - downgrade then upgrade works.
- [x] T006 [P] Unit tests `api/tests/unit/test_backup_crypto.py` (throwaway key):
  - encrypt to a recipient → the file is not the plaintext and starts with the age header;
  - decrypt with the identity gives the bytes back;
  - decrypt with a wrong identity fails cleanly;
  - `encrypt_file` streams (a 20 MB synthetic file, memory bounded);
  - no function accepts or writes a passphrase or an identity into `backup_dir` except `key.age` creation.
- [x] T007 [P] Unit tests `api/tests/unit/test_backup_store.py` (tmp dir):
  - snapshot id format `<YYYYMMDD-HHMMSS>-<kind>` (UTC) and parsing back;
  - `put_image` writes `images/<name>.age` once, and a second call does not rewrite (mtime unchanged);
  - only `<32 hex>.jpg` names are accepted;
  - a snapshot is complete only with `DONE`;
  - `history/` files are written atomically (temp + rename);
  - the layout of research R3.
- [x] T008 [P] Unit tests `api/tests/unit/test_backup_manifest.py`:
  - manifest build and read give the fields of data-model.md «manifest.json»;
  - validation refuses missing fields;
  - the serialised manifest has no key outside the documented list, and no value from a synthetic `.env`
    (a test that greps every secret value).

### Implementation

- [x] T009 Write `api/migrations/versions/0019_backups.py` for the tables of data-model.md, in particular:
  - data-model.md `backup_runs.status`, `backup_runs.kind` and `backup_runs.error_code` (checks);
  - data-model.md `backup_runs.requested_by` (FK users) and `backup_runs.snapshot_id` (unique, nullable);
  - the partial unique index on `backup_runs.status`;
  - data-model.md `backup_events.type` and `backup_events.result` (checks);
  - data-model.md `backup_status.id` (`= 1`).
- [x] T010 Add the models `BackupRun`, `BackupEvent` and `BackupStatus` in `api/app/models/backup.py`, and export them
  from `api/app/models/__init__.py`. Then run T005 green.
- [x] T011 [P] Implement `api/app/backup/crypto.py`: `age` through `subprocess`, streaming, no shell. Functions:
  - `encrypt_file`, `encrypt_stream` (to the recipient);
  - `decrypt_file`, `decrypt_stream` (with an identity path in tmpfs);
  - `sha256_file`.
  Then run T006 green.
- [x] T012 [P] Implement `api/app/backup/store.py`: layout, ids, `put_image`, `DONE`, history writer/reader, listing
  of snapshots (complete only). Then run T007 green.
- [x] T013 [P] Implement `api/app/backup/manifest.py`: dataclass, `to_json`/`from_json`, validation. Then run T008
  green.
- [x] T014 Run the whole api suite green. Batch 1 report: red then green for T005–T008. **Batch 1 commit.**

**Checkpoint**: tables, layout, encryption and manifest are ready.

---

## Phase 3: User Story 1 — Nightly automatic backup kept 30 days (P1) 🎯 MVP

**Goal**: one consistent encrypted snapshot of database + images every night, 30-day retention, no secrets.

**Independent Test**: spec US1: trigger the nightly job on synthetic data, see a `succeeded` run with counts; age
snapshots past 30 days and see only those removed.

### Tests (write first, run red)

- [x] T015 [P] [US1] Integration test `api/tests/integration/test_backup_snapshot.py` (test DB, tmp `uploads`, tmp
  `backup_dir`, throwaway key):
  - a snapshot holds `db.dump.age`, a `manifest.json` with the counts of the seeded data (requests, drafts, legacy,
    SAS, users, audit), `DONE`, and an object for every file in `uploads`, including legacy images;
  - decrypting the dump and `pg_restore --list` works;
  - each decrypted object matches its `sha256_plain`;
  - a second snapshot writes no new object for unchanged images;
  - `missing_referenced` is 0.
- [x] T016 [P] [US1] Integration test `api/tests/integration/test_backup_consistency.py` (research R4):
  - an image uploaded between pass 1 and the database snapshot is stored by pass 2;
  - a file referenced at the snapshot moment and deleted before pass 2 makes the run `failed` with
    `missing_images`, and the run is retried once;
  - an erasure (011) committed before the snapshot is not referenced, and its file is not required.
- [x] T017 [P] [US1] Unit tests `api/tests/unit/test_backup_retention.py`, cases inline:
  - snapshots older than 30 days by start time are selected, of every kind;
  - the newest successful snapshot is never selected, whatever its age;
  - an incomplete folder older than 1 day is selected; a younger one is not;
  - nothing is selected after a failed run;
  - GC removes only objects referenced by no kept manifest.
- [x] T018 [P] [US1] Unit tests `api/tests/unit/test_backup_disk.py`:
  - the estimate = new images + last dump size;
  - refuse with `disk_low` when free space after it would be under `backup_min_free_gb`;
  - accept otherwise.
- [x] T019 [P] [US1] Unit tests `api/tests/unit/test_backup_schedule.py` (clock fixture):
  - due when the Baghdad time has passed `backup_nightly_at` and no nightly snapshot exists for that Baghdad day;
  - not due twice the same Baghdad day;
  - catches up after a restart later the same day;
  - the day boundary is Baghdad midnight, not UTC.
- [x] T020 [P] [US1] Integration test `api/tests/integration/test_backup_serve.py`:
  - one loop iteration writes `backup_status` (heartbeat, free bytes);
  - a `requested` manual run is taken and ends `succeeded`;
  - a second operation while the advisory lock `160_016` is held refuses `busy`;
  - on start, a `running` row with no live lock becomes `failed/internal`.
- [x] T021 [P] [US1] Integration test `api/tests/integration/test_backup_mirror.py` (research R8):
  - the mirror tables are rebuilt from the files: snapshots → `backup_runs` matched on data-model.md
    `backup_runs.snapshot_id` (a manual request keeps its `id`; status `removed` for a vanished folder),
    `history/*.json` → `backup_events`;
  - deleting all mirror rows then syncing gives the same rows back.
- [x] T022 [P] [US1] Test `api/tests/integration/test_backup_no_secrets.py`:
  - with a synthetic `.env` whose values are unique markers, take a snapshot and decrypt every file;
  - no marker appears in any file under `backup_dir` (plaintext and decrypted);
  - no log line of the run contains a marker or a card field.

### Implementation

- [x] T023 [US1] Implement `api/app/backup/snapshot.py` (research R4):
  - pass 1;
  - exported `REPEATABLE READ` snapshot, then `pg_dump --snapshot` piped into `age`;
  - in the same transaction, the referenced names from `draft_images.file_name`, `request_images.file_name`,
    `legacy_images.file_name` and `card_readings.image_file_name`, the Alembic revision and the counts;
  - pass 2, verification of `sha256_enc` after writing (FR-015a), manifest, `DONE`;
  - the retry once on `missing_images`.
  Then run T015, T016 and T022 green.
- [x] T024 [US1] Implement `api/app/backup/retention.py` (research R6: selection, GC, disk estimate and guard). Then
  run T017 and T018 green.
- [x] T025 [US1] Implement `api/app/backup/mirror.py` (research R8, data-model.md tables). Failed runs are written
  to `history/<time>-failed.json`. Then run T021 green.
- [x] T026 [US1] Implement `api/app/backup/serve.py` and `api/app/backup/__main__.py` (`serve`, `now --kind`,
  `list`, `init-key`), with `api/tests/integration/test_backup_cli.py` (exit codes) and the key file
  `api/app/backup/keyfile.py` with `api/tests/integration/test_backup_keyfile.py`, both run red first. Cover the loop and the schedule of research R5, the advisory lock `BACKUP_LOCK = 160_016`, and the
  heartbeat and free space written into data-model.md `backup_status` fields. Logs carry ids, sizes and counts only.
  Then run T019 and T020 green.
- [x] T027 [US1] Add the `backup` service to `docker-compose.yml`:
  - same build as `api`, command `python -m app.backup serve`, `restart: unless-stopped`;
  - `uploads:/data/uploads:ro` and `backups:/data/backups`, on the default network only;
  - no port, no Docker socket;
  - healthcheck on the heartbeat.
  Add the named volume `backups`. Make the `api` image create `/data/backups` owned by 10001, mode 700.
- [x] T028 [US1] In `docker-compose.override.yml`, make development work without a configured key: `serve` logs
  «لم يُضبط مفتاح النسخ» and only writes the heartbeat. Add a dev throwaway key to `scripts/backup.sh init-key --dev`
  (written under the `backups` volume, the passphrase printed once).
- [x] T029 [US1] Run `docker compose up -d --build` locally, set `BACKUP_NIGHTLY_AT` two minutes ahead, and see a
  nightly run in `python -m app.backup list` (quickstart manual check 1). For SC-001, T019 also runs 7 simulated
  Baghdad days: one nightly each day.
- [x] T030 [US1] Run the whole api suite green. Batch 2 report: red then green for T015–T022. **Batch 2 commit.**

**Checkpoint**: backups exist every night locally; MVP reached.

---

## Phase 4: User Story 2 — Restore that is actually tested (P1)

**Goal**: verified restore of database + images together; weekly drill in an isolated throwaway stack.

**Independent Test**: spec US2 (backup → change → restore → identical; drill passes; drill on a damaged file fails).

### Tests (write first, run red)

- [ ] T031 [P] [US2] Integration test `api/tests/integration/test_backup_restore.py`:
  - verify refuses a snapshot whose `sha256_enc` does not match, before touching anything;
  - refuses a manifest whose Alembic revision is not in `api/migrations/versions`;
  - stage decrypts every image into a staging dir and checks `sha256_plain`;
  - the database restore into a scratch database gives the manifest counts.
- [ ] T032 [P] [US2] Integration test `api/tests/integration/test_backup_verify_restored.py`:
  - `verify-restored` passes on a faithful restore;
  - fails when a count differs, when a referenced image is missing, or when an image hash differs;
  - writes a `history/…-drill.json` with data-model.md `backup_events.result` `passed|failed` and the compared
    counts only.
- [ ] T033 [P] [US2] Write `scripts/backup-e2e.sh` (throwaway project `sijil-bk-e2e`, synthetic data, throwaway key
  and passphrase from stdin). It refuses to run on the server (`/opt/sijil` or `SIJIL_SERVER=1`). It asserts quickstart «Automated»:
  - backup → add a request and erase another → `restore.sh --yes-for-test` → counts and image hashes equal the
    snapshot;
  - the erased request is back;
  - a `pre_restore` snapshot exists;
  - the drill passes;
  - corrupting one object makes the drill and the restore fail with the live data unchanged.
  Run it red (the scripts do not exist).

### Implementation

- [ ] T034 [US2] Implement `api/app/backup/restore.py`: `verify`, `stage_images`, `restore_database` (drop/create +
  `pg_restore`), `verify_restored`. Cover research R7 and R9, and the restore and drill events in data-model.md
  `backup_events.details`. Then run T031 and T032 green.
- [ ] T035 [US2] Write `docker-compose.drill.yml` (research R9):
  - project `sijil-drill`: `db` on tmpfs, `api` from the live image, and a restorer;
  - one `internal: true` network, no ports, no shared volume with the live stack;
  - env file from a tmpfs path.
- [ ] T036 [US2] Write `scripts/restore.sh` (contracts/cli.md):
  - shows the snapshot, the loss warning (including «حذف مشترك»), and confirmation by typing the date;
  - takes `pre_restore`, then asks for the passphrase (identity only in tmpfs);
  - verifies, stages into a temporary volume, stops `api` and `backup`, restores, swaps `uploads` (owner 10001);
  - restarts, checks health, records the event and the audit line `backup.restore`;
  - supports `--from-external`.
  No server guard in `restore.sh` itself (it must work in a real disaster; the typed date protects it). The guard
  against the real server lives in `scripts/backup-e2e.sh` (analysis U2).
- [ ] T037 [US2] Write `scripts/backup.sh` with `init-key`, `now`, `list`, `status` and `drill [id] [--external]`.
  The drill brings up `docker-compose.drill.yml`, restores, runs `verify-restored`, records, and always runs
  `down -v` (trap).
- [ ] T038 [US2] Audit line `backup.restore` (actor none, entity snapshot id, after `{pre_restore}`), written by the
  restorer once the app is healthy (data-model.md «Audit»).
- [ ] T039 [US2] Run T033 `scripts/backup-e2e.sh` green on the developer machine.
- [ ] T040 [US2] Measure a full local restore with ~1 GB of synthetic images (SC-003, < 30 min) and note the time in
  the batch report. The owner re-measures it on the server after merge (analysis I1).
- [ ] T041 [US2] Check that the drill container has no network route out (`wget` to a public host fails inside it) and
  that its volumes are gone after `down -v`.
- [ ] T042 [US2] Run the whole api suite green. Batch 3 report: red then green for T031–T033. **Batch 3 commit.**

---

## Phase 5: User Story 3 — Main admin sees backup status and takes a manual backup (P2)

**Goal**: page «النسخ الاحتياطي», button «نسخة يدوية الآن», warnings on the page and the home page.

**Independent Test**: spec US3.

### Tests (write first, run red)

- [ ] T043 [P] [US3] API test `api/tests/integration/test_admin_backup_api.py` (contracts/api.md):
  - `GET /api/admin/backup` shape;
  - `runs` excludes `removed` and is newest first;
  - `POST /api/admin/backup/run` → 202, a `requested` row and the audit `backup.manual_requested`;
  - 409 `backup_busy` while one is requested or running;
  - 503 `backup_service_down` with an old heartbeat;
  - 403 for an added admin with every permission and for a marketer;
  - no personal data in the body.
- [ ] T044 [P] [US3] Unit tests `api/tests/unit/test_backup_warnings.py` (clock fixture), one case per code of
  contracts/api.md «Warning codes»: `last_failed`, `no_recent_backup` (36 h), `external_overdue` (8 days),
  `drill_failed_or_overdue` (8 days), `disk_low`, `service_down` (10 min). No warning on a healthy state.
- [ ] T045 [P] [US3] API test `api/tests/integration/test_admin_home_backup.py`: `GET /api/admin/home` carries
  `backup_warnings` for the main admin, and `[]` for other admins.
- [ ] T046 [P] [US3] Vitest `web/src/__tests__/backupPage.test.tsx`:
  - the page shows the last backup (Baghdad time), the kept runs, the last external copy, the last drill, the
    deploys, free space and the configured external path;
  - the button starts a run and shows «جارٍ النسخ…» then the result;
  - 409 shows «يوجد نسخ جارٍ الآن»;
  - warnings are listed with their Arabic texts.
- [ ] T047 [P] [US3] Vitest `web/src/__tests__/homeBackupWarning.test.tsx`: the home banner «فشل آخر نسخ احتياطي»
  (and the other texts) links to `/admin/backup`; it is absent when the list is empty.

### Implementation

- [ ] T048 [US3] Implement `api/app/services/backup_warnings.py` (research R12, from data-model.md `backup_runs`,
  `backup_events` and `backup_status.heartbeat_at`). Then run T044 green.
- [ ] T049 [US3] Implement `api/app/api/admin_backup.py` with the schemas in `api/app/schemas/backup.py`, main admin
  only, and register the router in `api/app/main.py`. Then run T043 green.
- [ ] T050 [US3] Add `backup_warnings` to `HomeOut` in `api/app/schemas/admin_requests.py` and to `api/app/api/admin.py`
  `home`. Then run T045 green.
- [ ] T051 [US3] Write `web/src/pages/admin/Backup.tsx` (MUI, Arabic, RTL, phone-width), replace `AdminBackup` in
  `web/src/pages/admin/placeholders.tsx` and `web/src/router.tsx`, and poll every 5 s while a run is active. Then run
  T046 green.
- [ ] T052 [US3] Add the warning banner to `web/src/pages/admin/Home.tsx`. Then run T047 green.
- [ ] T053 [US3] Playwright `e2e/tests/backup.spec.ts`: the main admin opens the page and presses «نسخة يدوية الآن»
  (fake-free e2e stack with a throwaway key); an added admin does not see the menu item.
- [ ] T054 [US3] Run both suites green. Batch 4 report: red then green for T043–T047. **Batch 4 commit.**

---

## Phase 6: User Story 4 — Weekly copy to the external drive (P2)

**Goal**: operator-run weekly copy to the hand-plugged drive, verified, never deleting, followed by the drill.

**Independent Test**: spec US4 with a temp folder or loop-mounted file system standing in for the drive.

### Tests (write first, run red)

- [ ] T055 [P] [US4] Integration test `api/tests/integration/test_backup_external.py`:
  - copy of the latest successful snapshot + missing objects + `key.age` to a target dir;
  - objects already on the target are reused, and nothing on the target is removed or overwritten;
  - verification re-reads `sha256_enc`;
  - refuse when the free space is too small, before writing;
  - writes `history/…-external.json` (data-model.md `backup_events.type` `external_copy`).
- [ ] T056 [P] [US4] Extend `scripts/backup-e2e.sh`:
  - `weekly` refuses a path that is not a mount point or has no `.sijil-external` marker, and writes nothing;
  - with a loop-mounted temp file system and `init-external` it succeeds, runs the drill on the copy and prints
    «يمكن فصل الهارد الآن»;
  - a second `weekly` adds only new objects.

### Implementation

- [ ] T057 [US4] Implement `api/app/backup/external.py` and the subcommand `external-copy`. Then run T055 green.
- [ ] T058 [US4] Add `init-external` and `weekly` to `scripts/backup.sh` (research R10): `mountpoint -q`, marker,
  `docker compose run --rm -v "$BACKUP_EXTERNAL_DIR":/external backup external-copy`, then `drill --external`, then
  `sync`.
- [ ] T059 [US4] Run T056 green.
- [ ] T060 [US4] Run the whole api suite green. Batch 5 report. **Batch 5 commit.**

---

## Phase 7: User Story 5 — One safe deploy path for staging and production (P2)

**Goal**: `scripts/deploy.sh` for both modes with a pre-deploy backup; `go-live`.

**Independent Test**: spec US5, on the developer machine only (a local stack with `APP_ENV=staging|production` in a
test env file and `NPM_NETWORK` pointing at a local network created for the test).

### Tests (write first, run red)

- [ ] T061 [P] [US5] Unit test `api/tests/unit/test_cli_go_live.py`:
  - `go-live` deactivates the demo accounts created by `seed-demo` (never deletes);
  - writes audit `system.go_live` with `{deactivated: N}`;
  - is idempotent;
  - leaves other accounts untouched.
- [ ] T062 [P] [US5] Write `scripts/deploy-e2e.sh` (local only, throwaway project and env files). Pre-flight
  refusals, with nothing changed:
  - `change-me` left in `.env`;
  - production with `OTP_MODE=fake`, `OCR_MODE=fake`, `DRIVE_MODE=fake` or `OTP_FAKE_CODE` set;
  - production with an active demo account;
  - a missing `BACKUP_DIR` or `key.age`;
  - a published port.
  And on success:
  - a `pre_deploy` snapshot is taken before the update;
  - a failed pre-deploy backup stops before `up`;
  - `seed-demo` runs only in staging;
  - a deploy event is recorded.
  The script refuses to run if it detects the server (`/opt/sijil` or `SIJIL_SERVER=1`). Run it red.

### Implementation

- [ ] T063 [US5] Add `go-live` to `api/app/cli.py`. Then run T061 green.
- [ ] T064 [US5] `git mv docker-compose.staging.yml docker-compose.server.yml`. Then:
  - add the `backup` bind `${BACKUP_DIR}:/data/backups` and `container_name: sijil-backup`;
  - update every reference (`scripts/`, `deploy/`, `README.md`, comments in compose files).
- [ ] T065 [US5] Write `scripts/deploy.sh` (research R11, contracts/cli.md exit codes). Reduce
  `scripts/deploy-staging.sh` to a wrapper that calls it. Record the deploy with `python -m app.backup record deploy …`.
- [ ] T066 [US5] Add the `record` subcommand (deploy events) to `api/app/backup/__main__.py`, following data-model.md
  `backup_events.details`.
- [ ] T067 [US5] Run T062 `scripts/deploy-e2e.sh` green on the developer machine.
- [ ] T068 [US5] Check that `docker compose -f docker-compose.yml -f docker-compose.server.yml config` publishes no
  port and that `backup` has no Docker socket mount.
- [ ] T069 [US5] Run the whole api suite green. Batch 6 report. **Batch 6 commit.**

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T070 [P] Write `deploy/backup.md` (Arabic), as FR-023 requires:
  - init-key, and where to keep the passphrase;
  - nightly backups, the manual backup, weekly with the drive, the drill;
  - restore from the server and from the drive, and restore on a new server (`.env` by hand);
  - opening a backup by hand with `age`;
  - every warning and what to do;
  - what the backups do not hold (`.env`, NPM).
- [ ] T071 [P] Rename `deploy/staging.md` to `deploy/server.md` and update it:
  - the compose file name and the alias;
  - the `BACKUP_*` variables, and the one-time `BACKUP_DIR` setup (owner 10001, mode 700);
  - go-live step 9 (`go-live`, then `APP_ENV=production`);
  - remove the old manual backup commands and the «الفيزة 015» note.
- [ ] T072 [P] Update `README.md` and `scripts/test-all.sh` (add `backup-e2e.sh` and `deploy-e2e.sh`, local only).
- [ ] T073 Security pass:
  - `git grep` for any key, passphrase or `age-secret-key` → none;
  - `.gitignore` covers local backup folders and dev keys;
  - log lines of every backup command carry no card field.
- [ ] T074 Run `scripts/test-all.sh` green, and `docker compose up` locally.
- [ ] T075 Write `specs/016-backup-deploy/manual-test-ar.md` (Arabic manual test steps from quickstart.md, local
  machine only), with a section «بعد الدمج على السيرفر»: 7 nights of backups (SC-001) and the restore time (SC-003).
- [ ] T076 Re-read `docs/system.md` §15 and §10 item 10 against the result. Update `docs/features.md` if an idea was
  postponed.
- [ ] T077 Mark the tasks done and set the spec status to Implemented. **Batch 7 commit.**

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 (Phase 3). US2 needs US1 snapshots. US3 needs the mirror (US1) and shows drill and
  external events (stubs until US2/US4). US4 needs US1 + the drill of US2. US5 needs `now --kind pre_deploy` (US1)
  and the `record` command.
- Order of batches: 1 → 2 → 3 → 4 → 5 → 6 → 7.

## Parallel Examples

- Batch 1: T005–T008 together; then T011, T012 and T013 together after T009/T010.
- Batch 2: T015–T022 are independent test files.
- Batch 4: T043–T047 together; T048 and T051 in parallel.

## Implementation Strategy

- MVP = batches 1–2 (nightly encrypted backups running). Batch 3 makes them trustworthy (restore and drill) and must
  follow before the field trial. Batches 4–6 add the page, the external copy and the deploy path.
- No batch touches the real server. The owner runs the first server set-up (`init-key`, `BACKUP_DIR`, first deploy)
  from `deploy/server.md` after the feature is merged.
