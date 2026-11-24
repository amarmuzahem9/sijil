# Research: Import of the Legacy Subscribers (014)

All Technical Context unknowns are resolved below. Each entry: Decision, Rationale, Alternatives considered.

## R1. Where the legacy subscribers live

- **Decision**: A new table `legacy_subscribers` (one row per imported Google Form row), with `legacy_images` for
  its card images and `legacy_imports` for each confirmed import. Not rows in `requests`.
- **Rationale**: Spec US4 / FR-017: legacy subscribers are not requests. A separate table means every request
  list, counter, commission, notification and «فتح طلب برقمه» stays untouched with no extra filters, and the 011
  deletion code (requests only) cannot reach them. The check engine (008) and the linked-record registry (010)
  were built with a source registry for exactly this (`legacy` named in their docstrings).
- **Alternatives**: rows in `requests` with a `legacy` status — rejected: every query in 008–013 would need a filter,
  and the status table (§7.2) has no such status. One generic `subscribers` table shared with SAS (015) —
  rejected: the two files share almost no columns (SAS has username, tower, expiry; legacy has family number, images,
  extras); 018 can present both through the same registries.

## R2. The check source

- **Decision**: `legacy_source` registered in `match_service` as `legacy`. It matches `phone` and `family_key` only,
  on rows with `counts_in_check = true`; `national_id` is never set; `pending` is always false. Registered at import
  of `app.services.legacy_import_service` from `app/main.py`, like `match_service`.
- **Rationale**: FR-011, FR-012, FR-021. The `Matches` views already give case 1 for a phone record and case 3
  (`family_only`) for a family record without national ID; the decision table, the early checks
  (`phone_checks`, draft checks), the submit check and the 010 re-check after a pin all call `find_matches`, so they
  get legacy records for free.
- **Alternatives**: a status filter at query time on the text «الحالة» — rejected: the rule «ملغي/مرفوض» is fixed at
  import into a boolean, so the check never parses text and the preview shows exactly what will count.

## R3. «الحالة»

- **Decision**: Store the raw value (`status_text`). `counts_in_check = status_text.strip() not in {"ملغي", "مرفوض"}`,
  computed at import and never changed in this feature. The preview shows the count per distinct status value and
  how many rows will not count.
- **Rationale**: Owner decision (clarification Q2). Exact match after trimming is predictable; any other spelling
  counts, which errs on the anti-fraud side (Principle I), and the admin sees the distinct values before confirming.
- **Alternatives**: fuzzy matching («ملغى», «ملغية») — rejected without the owner's list of variants; the preview's
  value counts make a variant visible, and the owner can ask for it.

## R4. Reading the file

- **Decision**: `.xlsx` via `openpyxl` (read-only mode, data only) with `defusedxml` installed; `.csv` via the
  standard library (UTF-8 with or without BOM). Header row matched by the 15 Arabic column names of §12.1 after
  trimming and collapsing spaces (the typo «البطافة» is accepted as written, and «البطاقة» too). Required: «الاسم
  الاول», «الرقم العائلي», «رقم الهاتف», «ID». At most 2 000 rows and 5 MB; the upload is parsed in memory and never
  written to disk.
- **Rationale**: Google Sheets exports both. `openpyxl` is pure Python, no system packages; `defusedxml` guards the
  XML parser. Not storing the file keeps real data out of the volume except in the tables meant for it.
- **Alternatives**: `pandas` — rejected: heavy for 109 rows. CSV only — rejected: the owner works in Sheets, and the
  xlsx export keeps the timestamp as a date cell.

## R5. Cleaning values

- **Decision**:
  - Phone: `app.core.phone` (§8.1). Invalid or empty → `phone = NULL`, flag `phone_invalid` / `phone_missing`.
  - Family number: kept as written (`family_number_file`), key via `app.core.family_key` (§6.2). An admin correction
    goes to `family_number`; the key is computed from the value in use. Length check counts the characters of the
    comparison key (≠ 18 → `family_length`).
  - Legacy number: trim, upper-case Latin, Arabic/Indic digits to Latin; valid shape `^T3C-\d{3}$` («T3C-1» is padded
    to «T3C-001»); otherwise flag `legacy_number_missing`.
  - Names: trim and collapse spaces only (system.md 1.19 §12.1); full name = first + second + third, skipping empty.
    A row with no first name is flagged `name_missing`.
  - Timestamp: an xlsx date cell, or the Sheets text forms `YYYY/MM/DD HH:MM:SS` and `DD/MM/YYYY HH:MM:SS`,
    interpreted as Baghdad time and stored in UTC (Principle X). Unreadable → NULL, not flagged.
  - Extras (mother's name, mother's father's name, birth date, both e-mails): stored as text in `extra` (JSONB),
    trimmed, never parsed or checked.
- **Rationale**: FR-004, FR-006, §12.1, §6.2; reuse of the tested normalizers keeps import and check consistent.

## R6. Flags and the per-row choice

- **Decision**: Flag codes, each with an Arabic label in the web:
  `family_dup_file`, `family_dup_legacy`, `family_length`, `family_missing`, `phone_invalid`, `phone_missing`,
  `phone_dup_file`, `phone_dup_legacy`, `in_sijil` (with request numbers), `legacy_number_missing`,
  `legacy_number_dup_file`, `already_imported`, `image_missing`, `image_failed`, `no_check_keys`, `name_missing`.
  Rows with `counts_in_check = false` skip the conflict flags (`*_dup_*`, `in_sijil`) as the spec says.
  A row is **ready** when it has no flag. A flagged row needs a choice `import` | `skip` (or `correct` with a value
  for `family_length`). `already_imported` rows are always skipped and need no choice. Repeated legacy numbers: at
  most one of the repeated rows may be `import`; `legacy_number_missing` and `name_missing` can only be `skip`.
  `in_sijil` lists only pending, approved and linked live requests (rejected and deleted never count, §6.1, §7.4).
- **Rationale**: FR-003 to FR-005, FR-020; one choice model for every flag keeps the page simple.

## R7. Fetching the Google Drive images

- **Decision**: A swappable adapter `drive_fetcher` (Principle VII) with `google` (httpx) and `fake` modes
  (`DRIVE_MODE`, refused as `fake` in staging/production like `OTP_MODE`). The file id is taken from
  `open?id=…`, `/file/d/<id>/` or `uc?id=…`; a cell with several links uses the first. Download from
  `https://drive.google.com/uc?export=download&id=<id>`, 30 s timeout, at most 15 MB, 4 at a time. An HTML answer
  means «not shared» (`not_shared`); other failures: `not_found`, `too_large`, `not_image`, `timeout`, `network`.
  The bytes are decoded with Pillow (JPEG or PNG; others → `not_image`), EXIF-rotated, reduced to 1 600 px on the
  longest edge and saved as JPEG quality 80 through `image_store` (new `save_bytes`), so stored legacy images obey
  the same limits as phone uploads.
- **Rationale**: FR-007, §12.1; the fake keeps tests and e2e free of the network and of real images (CLAUDE.md).
  Re-encoding strips metadata and caps size.
- **Alternatives**: Google Drive API with a service account — rejected: needs credentials and setup the owner did
  not ask for; §12.1 already says the files are shared by link at import time.

## R8. When images are fetched, and «nothing saved before confirmation»

- **Decision**: The upload creates a **preview** (`legacy_import_previews`, R9) and a background job (a
  `ThreadPoolExecutor`, like the 006 card-reading jobs) fetches every image into staged files in the uploads volume.
  The page polls the preview until `ready`. Staged files belong to the preview only; no `legacy_subscribers` row
  exists. On confirm, the rows and image rows are inserted in one transaction pointing to the staged files; on
  failure nothing is inserted and the preview stays. An expired, cancelled or superseded preview deletes its staged
  files. A preview still `fetching` when the process restarts becomes `failed` at startup.
- **Rationale**: The preview must show `image_failed` (FR-003), which requires fetching before confirmation; the
  all-or-nothing save (FR-006, SC-006) is then a pure database transaction. 218 images at 4 in parallel take a few
  minutes, too long for one HTTP request.
- **Alternatives**: fetch at confirmation — rejected: the admin would only learn of missing images after saving.

## R9. Preview storage and expiry

- **Decision**: Table `legacy_import_previews`: id (uuid), created_by, created_at, expires_at (created + 1 h),
  status (`fetching` | `ready` | `failed`), file_name, progress counters, and `rows` (JSONB: cleaned values, flags,
  fetch outcomes, staged file names, the admin's choices). One open preview per admin: a new upload cancels that
  admin's previous one. Expired previews and their files are removed on every upload and at startup;
  `draft_service.referenced_file_names` includes staged and legacy image files so `prune-orphans` never removes them.
- **Rationale**: The API may run more than one worker and may restart; a table survives both. The personal data in
  `rows` lives at most one hour and only for `reports` admins.

## R10. Confirmation, re-validation and concurrency

- **Decision**: Confirm takes a transaction-level advisory lock (one import at a time), re-runs the flag computation
  against the current database (new Sijil requests, legacy rows imported meanwhile), keeps the admin's choices for
  rows whose flags are unchanged, and refuses with `preview_changed` (409) if any row now needs a new choice; the
  preview is updated so the page shows those rows. Otherwise it inserts `legacy_imports`, the chosen
  `legacy_subscribers` and their `legacy_images`, writes the audit entry, deletes the preview row and commits. A
  unique constraint on `legacy_number` is the last guard.
- **Rationale**: Edge cases «concurrent imports» and «preview left unconfirmed»; FR-005, FR-020.

## R11. Audit

- **Decision**: One `audit_log` row, action `legacy_import`, entity `legacy_import:<id>`, `after` = file name and
  counts (rows in file, imported, skipped, already imported, not counted in check, incomplete, family numbers
  corrected). No phones, family numbers or names. A corrected family number is recoverable from the audit entry
  through `legacy_imports.id` → `legacy_subscribers` (`family_number_file`, `family_number`), which are never
  changed in this feature (constitution III, identity numbers by reference).
- **Rationale**: FR-009.

## R12. Showing the legacy record in the review file

- **Decision**: Register a `legacy` resolver in `linked_records`. `LinkedRecord` / `LinkedRecordOut` gain
  `legacy_number`, `incomplete` and `extra` (mother's name, mother's father's name, birth date; e-mails are not
  shown); `status` carries the raw «الحالة». The web `LinkedRecordCard` shows, for source `legacy`: source chip
  «مشترك قديم» (label change from «قديم»), the legacy number, name, phone, «تاريخ الاستمارة», «الحالة» as plain
  text (no request status colour), «غير مكتمل», «بيانات إضافية», and the images through a new route
  `/api/admin/legacy-images/{id}`. No family number (as for every linked record).
- **Rationale**: FR-015, FR-016, US3. Showing e-mails adds nothing to the admin's comparison (Principle VI).

## R13. Legacy image access

- **Decision**: `GET /api/admin/legacy-images/{id}` for review admins only (same 404 for everyone else), writes
  `image_access_log` with a new nullable column `legacy_subscriber_id` and `purpose = 'view'`.
- **Rationale**: §13, FR-016, Principle II.

## R14. Return to a legacy subscriber

- **Decision**: No code change: `submit_service._username` takes a historical username only from `sijil` refs, so a
  return whose target is legacy gets `{tower}-{phone}` (FR-013). A test pins this.

## R15. Import page

- **Decision**: Replace the «الاستيراد» placeholder with a page holding two tabs: «المشتركون القدامى» (this feature)
  and «مشتركو SAS» (shows «قريباً», 015). Steps on one page: choose file → «جارٍ سحب الصور N من M» → preview (counts,
  status values, flagged rows grouped by flag, each with «استيراد» / «تخطي» or a correction field, with
  «تخطي للكل» per group that sets «تخطي» on the group's rows; any row can still be changed afterwards — owner
  approved, system.md 1.19 §12.1) → «تأكيد الاستيراد» with a confirmation dialog → summary. The page is
  `reports`-only (already in `access.ts`).
- **Rationale**: US1, SC-003 (109 rows in under 15 minutes).
