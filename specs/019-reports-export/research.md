# Research: Reports and Export (019)

Inputs: [spec.md](./spec.md) (clarified 2026-11-27, all A), `docs/system.md` 1.25 §9, §10 item 8, §11, §13, §15; the
code as of `6c6c1d4`.

## R1. Permissions

- **Decision**: three checks, all on the server.
  - Report and export routes: `require_permission("reports")` (main admin implicit, marketers refused).
  - Identity in an export: `can_export_identity(user) = has_any_permission(reports) and can_review(user)`. Checked
    when the export is asked for, again when it is built, and again at every download.
  - Commission export: `require_permission("commissions")`, on the existing `/api/admin/commissions` router.
- **Rationale**: the same helpers 017/018 use (`core/access.py`, `review_service.can_review`); the 018 rule applies
  unchanged (FR-002, FR-009).
- **Alternatives**: a new `export_identity` toggle. Rejected (Q1 answer A: no new permission).

## R2. Period and date kind (Principle X)

- **Decision**: a pure module `core/report_period.py`: `period_bounds(kind, today, from_, to)` →
  `(start_utc, end_utc)` half-open, from Baghdad days. `week` = the Saturday on or before today through today; `month` =
  the 1st through today; `range` = `from` 00:00 through `to`+1 00:00 Baghdad. `from` > `to` or a missing date is
  refused (`period_invalid`). There is no maximum length (owner, analysis M2): the 5,000-row export limit is enough. The date kind picks `submitted_at` or `linked_at`; `linked_at` also implies
  `status = 'linked'` (the current link, 013).
- **Rationale**: the server owns the clock (`timeutil.baghdad_today`, `_set_clock_for_tests`), so the presets are
  tested with a fixed clock; the client sends only the kind and the two dates.
- **Alternatives**: the client computes the bounds. Rejected: two clocks, untested edges.

## R3. The report query and speed (SC-001)

- **Decision**: `services/report_service.py` builds one filtered `select` over `requests` (drafts live in another
  table, so they never appear). From it:
  - the page: 50 rows ordered by `(date DESC, id DESC)`, only the listed columns (no identity column is selected,
    whoever asks);
  - the total;
  - three `GROUP BY`s (status, tower, marketer) on the same filter.

  Names come from the values stored on the request (`tower_name`, `tower_code`, `plan_name`, `area_name`) and the
  marketer's user row (archived included).
  Migration 0021 adds `requests_submitted_at_idx (submitted_at DESC, id DESC)`; the link side already has
  `requests_linked_recent`.
- **Rationale**: 20,000 rows of one table with an index on the period column answer in tens of milliseconds;
  summaries are three small aggregates. Measured by `test_report_performance` (SC-001 < 2 s).
- **Alternatives**: materialized summaries. Rejected (Principle VI; not needed at this size).

## R4. Deleted requests

- **Decision**: a deleted request matches by its kept fields (its stored status, dates, tower, plan, marketer, type).
  It is listed with `deleted: true` and no name. In the sheet its row carries only the kept columns plus «محذوف» and
  the deletion reason. It gets no image link.
- **Rationale**: §7.4; the erased columns are already NULL by the `requests_erasure` constraint.

## R5. Export lifecycle

- **Decision**: an `exports` table (see [data-model.md](./data-model.md)) and a background job, following the
  legacy-import pattern:
  - a `ThreadPoolExecutor(max_workers=2)`;
  - a replaceable `submit` so tests run the job at once;
  - `sweep_at_startup` turns a `preparing` row left by a dead process into `failed`.

  Steps:
  1. `POST /api/admin/exports` checks the permissions, the period, at most one `preparing` per admin
     (`export_in_progress`), and the count: 0 gives `no_rows`, over 5,000 gives `export_too_large`. It then inserts
     `preparing` and submits.
  2. The job re-loads the requester and re-checks the permissions, re-runs the filter, and writes `requests.xlsx` and
     `manifest.json` into `EXPORTS_DIR/<id>/`. It then sets `ready` (row count, missing images, `expires_at =
     ready_at + 24 h`) and writes the audit entry (R8) in the same transaction.
  3. If anything fails, the state is `failed` (`error_code` only, no row data in the log) and the folder is removed.
- **Rationale**: the app stays usable (FR-017, SC-002); state survives a page reload; one admin cannot pile up jobs.

## R6. The ZIP is streamed at download, not stored

- **Decision**: only the sheet and a manifest (request number → stored image file names) are written at build time.
  The download streams a ZIP built on the fly with `zipfile` writing to an unseekable stream (data descriptors,
  ZIP64):
  - `requests.xlsx` first;
  - then, only for an identity export, `cards/T3C-<n>-<side>.jpg` read from `UPLOADS_DIR`, stored without
    compression (JPEGs do not shrink).

  An image erased between build and download (a later deletion, §7.4) is skipped and not sent. **Every image
  actually sent writes one `image_access_log` row** (user, image id, request id, side, `purpose = 'export'`), in
  the same transaction as the `export.downloaded` audit entry, before streaming starts (analysis C1, Principle II).
  Migration 0021 widens `image_access_log_purpose` to `IN ('view', 'ocr', 'export')`.
- **Rationale**: 5,000 requests × 2 images × ~300 KB ≈ 3 GB; storing it would threaten a 14 GB server disk
  (staging-server-capacity) and double the data at rest. The sheet is small (≈1–2 MB). Skipping an erased image is
  stricter than the spec's "the file is not changed" and honours §7.4. This is the one intentional deviation, noted in
  the plan.
- **Alternatives**: build the full ZIP on disk. Rejected for disk and data-at-rest. A new library (`zipstream-ng`).
  Rejected: the standard `zipfile` already streams.

## R7. Download without exposing the session

- **Decision**: the web app holds the access token in memory (bearer), so a plain `<a href>` cannot carry it, and a
  multi-GB blob in browser memory is unsafe on phones. So the download uses a ticket:
  - `POST /api/admin/exports/{id}/ticket` (bearer; requester only; permissions re-checked) returns a random 32-byte
    ticket, stored as a SHA-256 hash with `ticket_expires_at = now + 60 s`;
  - `GET /api/admin/exports/{id}/download?ticket=…` checks the hash, the expiry, the requester's current permissions
    and the state. It clears the ticket (single use), writes the «تنزيل تصدير» audit entry and streams the ZIP with
    `Content-Disposition: attachment`.
- **Rationale**: a leaked URL (browser history, proxy log) is useless after one use or 60 s; no long-lived secret in
  a URL. FR-012: refused to anyone but the requester.
- **Alternatives**: a cookie-scoped download path. Rejected: the refresh cookie is scoped to `/api/auth` only.

## R8. Audit entries (FR-011, §13)

- **Decision**: through `audit_service.record`:
  - `requests.exported`: `entity_type="export"`, `entity_id=<export id>`, with `after = {filters, row_count, numbers:
    [1001, …], identity: bool, missing_images}`. Written when the export becomes ready, which is when data leaves into
    a file.
  - `export.downloaded`: `{export_id, images}` (the number of images sent; each one is also in
    `image_access_log`, R6).
  - A build that fails writes no audit entry: no data left the database (analysis M1).
  - `commissions.exported`: `entity_type="commission_month"`, `{month}`.

  Filters are stored as ids and codes (area, tower, plan, marketer ids, status, type, dates); no name, phone or
  national ID. A test scans every export audit row for the synthetic names, phones and IDs.
- **Rationale**: "who, what, when"; request numbers are not personal data (the deletion entry of §7.4 holds one).

## R9. The sheet (FR-007, FR-008, FR-010, FR-012)

- **Decision**: `services/export_sheet.py` builds the workbook with openpyxl (already a dependency, 014):
  - right-to-left, Arabic headers, a frozen header row;
  - dates as Baghdad text `YYYY-MM-DD HH:MM`; money as integers;
  - the location as a Google Maps link (`https://maps.google.com/?q=lat,lng`).

  Two column sets, chosen by a pure function `columns(identity: bool)`:
  - the base set of FR-007;
  - with identity, also the national ID, the family number, birth date, issue and expiry dates, birth place and
    issuing authority, plus «صورة الوجه» and «صورة الظهر» as relative hyperlinks `cards/T3C-<n>-front.jpg`.

  A missing image reads «الصورة غير متوفرة».
  **Formula safety**: every text cell is written as a string (`data_type = "s"`) with the quote-prefix style, so a
  value starting with `=`, `+`, `-` or `@` stays text. Tests read the file back and assert no cell has type `f`.
- **Rationale**: one place decides the columns; an identity column cannot appear by accident in the base set
  (tested).

## R10. Where files live, and backups (FR-013, SC-006)

- **Decision**:
  - files go in a new Docker volume `exports`, mounted only on `api` at `/data/exports` (`EXPORTS_DIR`, default
    `/data/exports`);
  - `backup` does not mount it, and the backup snapshot already copies only image-named files from `uploads`;
  - `sweep_expired()` removes the folders of `ready` rows past `expires_at` and of `failed` rows. It sets `removed` and
    runs at startup, on every exports call, and every 15 minutes from a task started in `lifespan` (not in tests).
- **Rationale**: not in backups by construction; removal does not depend on someone opening the page.
- **Alternatives**: a folder in `uploads`. Rejected: that volume is backed up and mounted read-only by `backup`.

## R11. Commission export (FR-015)

- **Decision**: `GET /api/admin/commissions/export?month=YYYY-MM` builds the xlsx synchronously from
  `commission_service.report(db, month)` and `detail(db, month, marketer_id)` per row (the same functions the page
  uses). It has two sheets, «العمولات» and «الطلبات». The amounts come from `ReportRow.figures` (locked for a paid month)
  and alerts from `ReportRow.alerts`. The route writes `commissions.exported` and returns the bytes (`apiFetchBlob`; the
  file is tens of KB). Nothing is stored.
- **Rationale**: no second calculation path, so SC-005 holds by construction; a test also compares cell by cell with
  the report API after a tier change.

## R12. Reports page shows no money (FR-016)

- **Decision**: the report schema has no amount, rate or payment field; a test asserts the JSON keys of the report and
  the sheet headers contain none of them.

## R13. Filter options

- **Decision**: `GET /api/admin/reports/options` returns areas, towers, plans (active and inactive, names as stored
  now) and marketers (archived and stopped included, marked). Filtering is by id; rows show the names stored on the
  request.

## R14. Tests (Principle VIII; each test red first)

- unit:
  - `test_report_period` (week from Saturday, month, range, 23:59/00:00 edges, invalid ranges);
  - `test_export_sheet` (columns per identity flag, formula safety, deleted rows, missing image, relative links, RTL).
- integration:
  - `test_reports_api` (filters, date kind, undone link, deleted, summaries add up, paging, options);
  - `test_reports_privacy` (the permission matrix: main admin, reports, reports+review, review only, commissions only,
    marketer; identity keys absent; no money keys);
  - `test_exports_api` (lifecycle, no_rows, too large, in progress, identity forbidden, ticket single use / expiry /
    other admin, permission lost before download removes an identity file, ZIP contents and names, erased image
    skipped, audit entries and no personal data);
  - `test_exports_sweep` (expiry, failed, startup);
  - `test_commission_export` (equals the report for a paid and an unpaid month after a tier change, alerts, archived
    marketer, no phone or ID, audit);
  - `test_report_performance` (20,000 synthetic requests; report < 2 s; export of 1,000 with images < 2 min).
- web (Vitest from PowerShell): `reports.test.tsx` (filters, summaries, box shown only when allowed, states);
  `commissionsExport.test.tsx`.
- e2e (Playwright): `reports-export.spec.ts`: filter, export with images as the main admin, download and inspect
  the ZIP; a `reports`-only admin has no box; a marketer is refused.
