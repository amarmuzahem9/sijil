# Research: Import of the SAS Subscribers (015)

Technical Context has no open unknowns. Each entry: Decision, Rationale, Alternatives considered.

## R1. Where the SAS subscribers live

- **Decision**: New tables `sas_subscribers` (one row per SAS username), `sas_imports` (one row per confirmed
  import), `sas_subscriber_changes` (append-only field changes), `sas_tower_mappings` and `sas_import_previews`.
  They are not rows in `requests` or `legacy_subscribers`.
- **Rationale**: Same reasoning as 014 R1. Requests, counters, links, notifications and «فتح طلب برقمه» stay out of
  reach with no extra filter (FR-016, FR-017, FR-020). SAS rows share almost no columns with legacy rows (username,
  tower, expiry against family number, images, extras). The check engine and the linked-record registry already take
  `sas` as a source name.
- **Alternatives**: a shared `subscribers` table for legacy and SAS. Rejected: the two have different keys (legacy
  number against username) and different re-import rules (insert-only against update). 018 can show both through the
  registries.

## R2. Reading the file

- **Decision**: Reuse `legacy_file.read_table` with new keyword limits (`max_bytes`, `max_rows`; the legacy defaults
  stay 5 MB / 2 000). SAS limits are 15 MB and 50 000 rows. Headers are matched after trimming and lower-casing:
  `id, username, firstname, lastname, phone, expiration, notes, parent_name, created_at, last_online, group_name`.
  `username` and `phone` are required (`import_columns_missing`). Unknown columns are ignored. The upload is parsed in
  memory and never written to disk.
- **Rationale**: FR-002. One reader keeps the xlsx/csv handling and its safety (defusedxml, zip check) in one place.
  A SAS export of 20 000 rows is a few MB.
- **Alternatives**: streaming row by row into the preview. Rejected: the flags need the whole file (repeated
  usernames), and 50 000 rows fit in memory easily.

## R3. Never keeping `ct_password`

- **Decision**: `sas_row.match_headers` maps only the allowed headers to their column index. Any header that is
  `ct_password`, or that contains `password` (any case), is never mapped. Rows are built only from mapped indexes,
  right after `read_table` returns. The full cell lists are then dropped, and no code path logs, returns or stores
  them. Error messages name columns, never cell values. A test uploads csv and xlsx files whose `ct_password` cells
  hold unique synthetic markers. It then searches every `sas_*` table (as text), the preview JSON, `audit_log`, the
  API responses and the captured log output, and none of them may contain a marker (SC-003).
- **Rationale**: FR-003, constitution II. The parser has to tokenise the whole row, but the value never leaves the
  reader's temporary list and never becomes data in Sijil. That is the practical meaning of «لا يُقرأ ولا يُخزَّن».
- **Alternatives**: asking the admin to delete the column before upload. Rejected: it is easy to forget, and the
  rule must hold on the server.

## R4. Username, prefix and tower

- **Decision**:
  - Username: trimmed and kept as written (`username`). Its key `username_key` is the upper-case value with
    Arabic/Indic digits made Latin, and it is unique. An empty username gives the flag `username_missing` (skip only).
  - Split: the last `-`-separated segment is normalised by §8.1. If it is a valid phone, it is `username_phone` and
    the rest (before that last dash) is the **prefix**. Otherwise `username_phone` is NULL and the prefix is NULL
    (the row is counted «يوزر بلا هاتف» and has no tower).
  - Tower rule: the prefix with dashes and spaces removed, upper-cased, equal to an existing `towers.code`, active or
    stopped (`KZF06` → KZF06, `RBD-01S` → RBD01S, `SMR-01` → SMR01).
  - A prefix with no rule match uses `sas_tower_mappings` if the admin saved one before (a tower or «بلا برج»).
    Otherwise it goes to the preview's mapping table, keyed by the upper-cased prefix. Confirmation needs a mapping
    for every listed prefix (FR-007). The rule wins over a saved mapping. Saved mappings appear in the table as
    «من استيراد سابق» and can be changed.
- **Rationale**: FR-005, §12.2, Assumptions (tower is information only). Tower codes are `^[A-Z0-9]{2,20}$` (004),
  so removing the dashes is what makes `RBD-01S` comparable.
- **Alternatives**: one regex per known shape. Rejected: «remove dashes and look up» covers all three known shapes
  plus any new tower without code changes.

## R5. Phones

- **Decision**: `phone` = the phone column normalised by §8.1, or NULL. `phone_file` keeps the written value.
  `username_phone` comes from R4. Both count in the check (FR-012), and when both exist and are equal only one match
  is reported. A row where neither exists is counted «بلا هاتف صالح» and never matches.
- **Rationale**: Owner decision Q1 (A).

## R6. Dates

- **Decision**: `expiration`, `created_at` and `last_online` accept an xlsx date cell or text `YYYY-MM-DD[ HH:MM[:SS]]`
  (also `/`). They are read as Baghdad time and stored as UTC `timestamptz`. Empty, or SAS «never» values like
  `0000-00-00…`, give NULL with no count. Any other unreadable value gives NULL and the count «تاريخ غير مقروء». The
  review file shows expiry as a Baghdad date with «منتهي» when it is before today.
- **Rationale**: Edge case «Unreadable dates», US3 scenario 2, Principle X.

## R7. Comparing with stored rows (re-import)

- **Decision**: Each file row is looked up by `username_key`:
  - not stored → `new`;
  - stored with every compared field equal → `unchanged`;
  - otherwise → `update`, with the list of changed fields.
  Compared fields: sas_id, username (as written), first_name, last_name, phone, phone_file, username_phone, tower
  (after rule or mapping), expires_at, sas_created_at, last_online_at, group_name, parent_name, notes. Stored rows
  whose key is absent from the file become `missing`: their `missing_since` is set at confirmation if it is NULL,
  and is cleared when a later file holds them again. «تخطي» on an `update` row leaves the stored row as it is (and it
  is not marked missing). «تخطي» on a `new` row adds nothing.
- **Rationale**: FR-021, FR-022 (owner decision Q2: A). An unchanged row writes nothing, so a weekly re-import of an
  almost identical file stays fast and its history stays small.

## R8. The check source

- **Decision**: `sas_source` is registered in `match_service` as `sas`. It matches when `phone = :p OR
  username_phone = :p`, with both columns indexed, on every row (missing rows included). It never sets
  `national_id`, `family` or `pending`. Registered from `app/main.py` like `legacy_source`.
- **Rationale**: FR-011, FR-012, FR-022. `phone_checks`, the draft checks, the submit check and the 010 re-check
  all call `find_matches`, so they see SAS records without changes, and a phone record gives case 1.
- **Alternatives**: none worth weighing. A source is the extension point 008 built for this.

## R9. Flags and choices

- **Decision**: These flags need a choice:
  - `username_missing`: skip only.
  - `username_dup_file`: one row per key may be `import`, and the others must be `skip`. It is listed with the other
    row numbers.
  - `phone_in_sijil`: `import` | `skip`. Shown with the request numbers. It is raised when the row is `new`, or an
    `update` whose phones changed, and one of its phones is held by a pending, approved or linked live request whose
    upper-case username differs.
  «تخطي للكل» per group sets `skip` on the group's rows (the client sends the choices). Informational counts with no
  choice: `same_username_in_sijil` (FR-018), `no_valid_phone`, `username_no_phone`, `date_unreadable`,
  `phone_dup_file`, `phone_in_legacy`, `missing_from_file`. Rejected and deleted requests never count (§6.1, §7.4).
- **Rationale**: FR-004, FR-006, FR-007, FR-018. The 014 choice model, minus `correct` (SAS values are not
  corrected in Sijil).

## R10. Audit and change history

- **Decision**: One `audit_log` row per confirmation:
  - action `sas.imported`, entity `sas_import` and its id;
  - `after` = file name and counts: rows, added, updated, unchanged, skipped, missing_marked, missing_cleared,
    without_phone, prefixes_mapped.
  No usernames, phones or names. Every `update` writes one `sas_subscriber_changes` row (import id, subscriber id,
  `before` and `after` JSON of the changed fields only). Every mapping saved or changed is written in the
  `sas_tower_mappings` row (set_by, set_at, import id), and the audit counts it.
- **Rationale**: FR-009, constitution III («subscriber data edit» with before/after). The audit line links to
  `sas_imports.id`, and from there to the change rows. This is the by-reference pattern of 010 pins, so the phone
  values stay out of the audit text.
- **Alternatives**: one audit line per changed row. Rejected: thousands of lines per import, and each would carry
  phones.

## R11. Logs

- **Decision**: Log lines carry the preview or import id and counts only. Never a username (it contains the phone),
  phone, name, file name, or request URL with a username. The upload route is excluded from body logging like
  014's.
- **Rationale**: FR-009, §13. 014 batch 6 already removed request URLs from the access logs.

## R12. Preview, expiry, concurrency

- **Decision**: `sas_import_previews` works like 014 (id, created_by, created/expires_at + 1 h, file_name, `rows`
  JSONB, `prefixes` JSONB, counts). Status is always `ready`, because there is no job. One open preview per admin.
  Expired previews are swept on upload and at startup. Confirm takes **the same** advisory lock as the legacy confirm
  (`_CONFIRM_LOCK`, moved to a shared module), so a SAS confirm and a legacy confirm never run at once. It then
  re-runs the comparison and flags against the database and refuses with `preview_changed` (409, updated preview) when
  a row that needs a choice changed, or when a new unknown prefix appears. Otherwise it writes everything in one
  transaction. Rows are inserted and updated in batches of 1 000.
- **Rationale**: Edge cases «Concurrent imports», «A preview left unconfirmed», «A failed save»; SC-007.

## R13. The review file

- **Decision**: Register a `sas` resolver in `linked_records`. `LinkedRecord` / `LinkedRecordOut` gain `expiry_as_of`
  (date of the last import that wrote the row), `last_online`, `group_name`, `username_phone` (only when it differs
  from `phone`) and `missing_from_file` (date or null). `expiry`, `username`, `phone`, `tower_code`, `tower_name`
  (current names of the tower) and `registered_at` (= SAS created_at) are filled. No images, no request number.
  `LinkedRecordCard` shows source «مشترك SAS» and «تاريخ الانتهاء: … (حسب آخر استيراد …)», with «منتهي» when past.
- **Rationale**: FR-015, US3. The 010 docstring already reserves `expiry` for SAS.

## R14. Return to a SAS subscriber

- **Decision**: `submit_service._username`: if the target set has Sijil refs with a username, the newest one wins (as
  today). Otherwise the SAS ref with the newest `last_import_id`, then the highest id, gives its username as written.
  Otherwise `{tower}-{phone}`.
- **Rationale**: FR-013, §6.3 item 4. Request usernames are not unique in the database (0010), so taking a SAS
  username is safe.

## R15. Tower usage

- **Decision**: Register a tower usage check: a tower referenced by any `sas_subscribers.tower_id` or
  `sas_tower_mappings.tower_id` counts as used. The settings page then refuses to delete it or edit its code (§10.6).
  Foreign keys are `ON DELETE RESTRICT`.
- **Rationale**: §10.6 «لا يرتبط به أي طلب أو مشترك»: changing a mapped tower's code would silently break the rule
  of R4.

## R16. Import page

- **Decision**: The «مشتركو SAS» tab replaces «قريباً». It shows:
  1. Choose a file.
  2. The preview: counts (new, updated, unchanged, missing from file, without a valid phone, same username in Sijil,
     unreadable dates).
  3. The mapping table: prefix, rows, a tower select with «بلا برج», and «من استيراد سابق» when pre-filled.
  4. The flagged groups with «استيراد» / «تخطي» per row and «تخطي للكل» per group.
  5. «تأكيد الاستيراد» with a dialog.
  6. The summary: skipped rows listed by SAS id and row number.
  Groups over 200 rows are paged on the page. `reports` only (already in `access.ts`).
- **Rationale**: US1, US5, FR-010, SC-004.
