# Implementation Plan: Deployment and Backups

**Branch**: `016-backup-deploy` | **Date**: 2026-11-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/016-backup-deploy/spec.md` (clarified; `docs/system.md` 1.21 §15)

## Summary

A new compose service `backup` (same image as `api`, plus `pg_dump` 16 and `age`) runs a loop. Every night at 03:00
Baghdad, and when the main admin presses «نسخة يدوية الآن», it takes one snapshot:
- the database, captured in one exported snapshot;
- every card image in `uploads`, mounted read-only (marketers' images and the 014 legacy images).

Everything is encrypted to a public `age` recipient. The matching identity is kept in `key.age`, protected by the
owner's passphrase, which never touches the server. So the server can encrypt but never decrypt. Images are stored
once as write-once encrypted objects shared by all snapshots. Snapshots older than 30 days are removed, never the
newest good one.

Host scripts cover the operator's work:
- **Weekly copy** to the hand-plugged external drive: marker-checked, never deletes, verified. It then runs a restore
  drill on that copy, in an isolated network-less throwaway stack.
- **Verified restore**: stage, then swap, after taking a pre-restore snapshot.
- **Single deploy script** for staging and production: always takes a pre-deploy snapshot, refuses fake modes and
  active demo accounts in production, and `go-live` deactivates the demo accounts.

The backup files are the truth. The database tables only mirror them for the main admin's «النسخ الاحتياطي» page and
the home warnings, so a restore does not erase the backup history.

## Technical Context

**Language/Version**: Python 3.12 (api + backup service), Bash (operator scripts), TypeScript + React 18 (web)

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic (existing). New system packages in the api image:
`postgresql-client-16` (PGDG apt repo), `age` (Debian). **No new Python or npm package.**

**Storage**: PostgreSQL 16 (mirror tables, migration `0019_backups`); host folder `BACKUP_DIR` (server) / named
volume (local); external drive at `BACKUP_EXTERNAL_DIR`

**Testing**: pytest in the `api` container, `scripts/backup-e2e.sh` (throwaway compose project), Vitest, Playwright

**Target Platform**: the company Linux server, Docker Compose behind Nginx Proxy Manager

**Project Type**: web application (api + web) + operator scripts

**Performance Goals**: nightly backup of field-trial data (~1–2 GB images) in minutes with no user-visible slowdown;
restore < 30 min (SC-003)

**Constraints**: 14 GB free disk shared with the 4.3 GB ocr image (margin 2 GB); passphrase never on the server; no
Docker socket in any container; no published port; the app containers never mount the backups

**Scale/Scope**: hundreds to thousands of requests, 109 legacy subscribers, ~20 000 SAS rows; 1 new service, 3 tables,
2 API routes + 1 changed, 1 admin page, 3 scripts (+ wrapper), 1 CLI command, docs

## Constitution Check

| Principle / constraint | Status |
|---|---|
| I Anti-Fraud First | Not touched. A restore brings back the data as it was; checks run on whatever is in the database. ✅ |
| II Identity documents | Backups are encrypted (age), readable only with the off-server passphrase. The backup folder is mode 700 and never mounted by api/web. Manifests, history, logs and the page hold no personal data. The drill handles real images only in a network-less container and keeps no results. ✅ |
| III Audit trail | Manual backup requested, restore and go-live are audited without personal data. Nothing is physically deleted by the app. Removal of expired backups is §15 retention, not deletion of requests. §7.4 erased data stays in backups until expiry, as documented. ✅ |
| IV Immutable values | A restore returns values to a past state. That is an operator recovery action, warned and audited, not an edit. ✅ |
| V Mobile-first, Arabic | Page and messages in Arabic. The page is main-admin desktop, but works on phone width. ✅ |
| VI Simplicity | One service, the same image, `age` and `pg_dump`. No restic/borg/cron. Writing our own deduplication (R3) is justified by the encrypt-only rule. ✅ |
| VII Fixed stack | Compose services are now `db`, `api`, `ocr`, `web`, `backup` (+ local `proxy`). `backup` is the api code with another command, not a new technology. ⚠️ Constitution «Additional Constraints» already requires backups. No amendment needed, noted in Complexity Tracking. |
| VIII Tested rules | Retention, consistency, disk guard, permissions and warnings are covered by tests written red first; full cycle in `backup-e2e.sh`. ✅ |
| IX Server-side authorization | Main admin only, enforced in the API. ✅ |
| X Time | UTC stored; nightly day and display in Baghdad. ✅ |
| Secrets | `.env` and the passphrase never in backups or git. `BACKUP_AGE_RECIPIENT` is public. `.env.example` documents the new variables. ✅ |
| Backups constraint | Nightly 30 days, weekly external, tested restore (drill every week). ✅ |

**Post-design re-check**: no violation. Gate passed.

## Project Structure

### Documentation (this feature)

```text
specs/016-backup-deploy/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md
│   └── cli.md
├── checklists/requirements.md
└── tasks.md              # /speckit-tasks
```

### Source Code (repository root)

```text
api/
├── Dockerfile                         # + postgresql-client-16, age
├── app/backup/                        # new package: python -m app.backup <serve|now|list|verify-restored|record|…>
│   ├── __main__.py
│   ├── snapshot.py                    # passes 1–3, manifest (R4)
│   ├── crypto.py                      # age encrypt/decrypt via subprocess (R2)
│   ├── store.py                       # layout, objects, DONE, history files (R3)
│   ├── retention.py                   # 30 days, newest kept, GC, disk guard (R6)
│   ├── mirror.py                      # files → tables (R8)
│   ├── serve.py                       # loop, schedule, requests, lock (R5)
│   └── restore.py                     # verify, stage, db restore, verify-restored (R7, R9)
├── app/models/backup.py               # backup_runs, backup_events, backup_status
├── app/api/admin_backup.py            # GET /api/admin/backup, POST /api/admin/backup/run
├── app/services/backup_warnings.py    # R12; used by admin home
├── app/cli.py                         # + go-live
├── migrations/versions/0019_backups.py
└── tests/{unit,integration}/test_backup_*.py
web/src/pages/admin/Backup.tsx         # replaces the placeholder
web/src/pages/admin/Home.tsx           # backup warning banner
web/src/__tests__/backup*.test.tsx
e2e/                                   # + backup page case
docker-compose.yml                     # + backup service, backups volume
docker-compose.server.yml              # renamed from docker-compose.staging.yml; + BACKUP_DIR bind
docker-compose.drill.yml               # isolated drill project (R9)
scripts/deploy.sh, deploy-staging.sh (wrapper), backup.sh, restore.sh, backup-e2e.sh
deploy/staging.md → deploy/server.md   # install, update, go-live
deploy/backup.md                       # backups, weekly, restore, new server, manual age decryption, warnings
.env.example                           # + BACKUP_* (contracts/cli.md)
```

**Structure Decision**: existing `api/` + `web/` layout. The backup code lives in `api/app/backup/`, so it reuses the
models and migrations; it runs only in the `backup` container and in one-off operator containers.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| Own deduplicated encrypted store (R3) | 30 nightly snapshots must fit 14 GB, and encryption must work without the passphrase | restic/borg need the symmetric key on the server; full tars do not fit |
| Fifth compose service `backup` | The app containers must never read backups; the schedule must survive restarts | Code in `api` would expose backups to the app; host cron is invisible to the page and untested |
| Files as truth + DB mirror (R8) | A restore must not erase the history of later backups | History only in the DB is lost on every restore |
