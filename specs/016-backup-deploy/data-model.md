# Data Model: Deployment and Backups (016)

Two kinds of state: the **backup files** (source of truth, `BACKUP_DIR`, research R3) and a **database mirror** for the
admin page (R8). Neither holds personal data. Migration `0019_backups`.

## Files (BACKUP_DIR and the external drive)

| Path | Content | Encrypted |
|---|---|---|
| `key.age` | age identity protected by the owner's passphrase | yes (passphrase) |
| `images/<32 hex>.jpg.age` | one stored card image, written once | yes |
| `images/<32 hex>.jpg.age.meta` | its size, `sha256_plain`, `sha256_enc` (so a later snapshot needs no re-read) | no |
| `snapshots/<id>/db.dump.age` | `pg_dump -Fc` of the whole database | yes |
| `snapshots/<id>/manifest.json` | see below | no (no personal data) |
| `snapshots/<id>/DONE` | written last; marks a complete snapshot | no |
| `history/<utc time>-<type>.json` | one drill / external copy / restore / deploy event | no |

Snapshot id: `<YYYYMMDD-HHMMSS UTC>-<kind>`, kind ∈ `nightly | manual | pre_deploy | pre_restore`.

**manifest.json**: `format` (1), `id`, `kind`, `started_at`, `finished_at` (UTC ISO), `app_commit`, `alembic_revision`,
`counts {requests, drafts, legacy_subscribers, sas_subscribers, users, audit_entries}`,
`dump {size, sha256_enc}`, `images [{name, size, sha256_plain, sha256_enc}]`, `missing_referenced` (must be 0),
`total_size` (dump + images new to this snapshot), `requested_by` (user id or null).

## Tables (mirror)

### `backup_runs`
| Column | Type | Rules |
|---|---|---|
| `id` | text PK | never changes: `req-<uuid>` for a manual request, otherwise the snapshot id |
| `snapshot_id` | text null, unique | the snapshot folder id; null until the run starts. The mirror (R8) matches files on this column |
| `kind` | text | `nightly|manual|pre_deploy|pre_restore` |
| `status` | text | `requested|running|succeeded|failed|removed` |
| `error_code` | text null | `disk_low|missing_images|dump_failed|encrypt_failed|verify_failed|busy|internal` |
| `requested_by` | bigint null FK users | manual only |
| `started_at`, `finished_at` | timestamptz null | UTC |
| `total_size`, `image_count` | bigint null | |
| `counts` | jsonb null | as in the manifest |
| `removed_at` | timestamptz null | set when retention removed it (status `removed`) |
| `created_at` | timestamptz | row creation, for ordering |

Partial unique index: one row with `status IN ('requested','running')`. Failed runs keep a row (from a small
`history/…-failed.json`), so the page shows failures.

### `backup_events`
| Column | Type | Rules |
|---|---|---|
| `id` | text PK | history file name |
| `type` | text | `drill|external_copy|restore|deploy` |
| `at` | timestamptz | UTC |
| `result` | text | `passed|failed` (drill), `succeeded|failed` (others) |
| `snapshot_id` | text null | the snapshot concerned |
| `details` | jsonb | drill: counts compared, reason; external: size, location label; deploy: mode, old/new commit, pre-deploy snapshot; restore: pre-restore snapshot. Never personal data. |

### `backup_status` (single row, id = 1)
`heartbeat_at`, `free_bytes`, `total_bytes`, `min_free_bytes`, `nightly_at` (text `HH:MM` Baghdad),
`external_dir` (configured path, read-only display), `backup_dir_bytes`, `key_configured` (false until
`BACKUP_AGE_RECIPIENT` is set; the service then backs nothing up and the page says so).

## State transitions — backup run

`requested → running → succeeded | failed` (`snapshot_id` set on `running`); `running → failed` also on crash (on start `serve` marks any `running`
row without a live lock as `failed/internal`); `succeeded → removed` by retention. A `failed` row never removes
anything.

## Audit (existing `audit_log`)

| action | actor | entity | after |
|---|---|---|---|
| `backup.manual_requested` | main admin | `backup_run`, run id | `{}` |
| `backup.restore` | none | `backup_run`, snapshot id | `{pre_restore: id}` |
| `system.go_live` | none | `system`, `-` | `{deactivated: N}` |
