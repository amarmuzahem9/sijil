---

description: "Task list for feature 015: Import of the SAS Subscribers"
---

# Tasks: Import of the SAS Subscribers

**Input**: Design documents from `specs/015-sas-import/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's rule: **each new test is run red before its
code is written**. Report red and green for every test task.

**Test rules**:
- Synthetic data only: made-up usernames, names, phones, and `ct_password` markers `SYNTH-PW-<n>`. No real SAS export
  or subscriber data (CLAUDE.md).
- Requests come from `api/tests/helpers/requests.py::request_factory`, admins from
  `api/tests/helpers/review.py::admin_with`, and time from the clock fixture of `api/tests/conftest.py`.
- Vitest runs from PowerShell (project note). Host edit scripts write LF (project note).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each one ends at a phase boundary, with a commit):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T013 |
| 2 | 3a (US1 preview, API) | T014–T021 |
| 3 | 3b (US1 choices, confirm, page) | T022–T031 |
| 4 | 4 (US2 check source, username) | T032–T037 |
| 5 | 5–7 (US3 review file, US4 isolation, US5 re-import) | T038–T051 |
| 6 | 8 (Polish, e2e, manual test) | T052–T058 |

---

## Phase 1: Setup

- [x] T001 Confirm the baseline. Run `docker compose up -d`, then check that `docker compose exec api pytest` and
  `cd web && npm test` are green on the branch before any change. Note the counts in the batch report.
- [x] T002 [P] Add error codes with Arabic messages to `api/app/errors.py`: `tower_not_found` (the import codes of 014
  are reused: `import_file_unreadable`, `import_columns_missing`, `import_too_many_rows`, `import_file_too_large`,
  `preview_not_found`, `preview_choices_missing`, `preview_changed`, `choice_not_allowed`; contracts/api.md).
- [x] T003 [P] Move `_CONFIRM_LOCK` from `api/app/services/legacy_import_service.py` to a shared
  `api/app/services/import_lock.py` (`IMPORT_CONFIRM_LOCK`, the same value 140_014) and use it from the legacy
  confirm (research R12). The legacy suite must stay green.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the tables, the shared file reader limits, and the pure row rules that every story uses.

### Tests (write first, run red)

- [x] T004 [P] Migration test `api/tests/integration/test_migration_0018.py`:
  - the five tables of data-model.md exist;
  - data-model.md `sas_subscribers.username_key` is unique;
  - `sas_subscribers.phone` and `sas_subscribers.username_phone` refuse a non-§8.1 value and accept NULL;
  - `sas_subscribers.tower_id` and `sas_tower_mappings.tower_id` restrict a tower delete;
  - `sas_tower_mappings.prefix` is the primary key;
  - no table has a column whose name contains `password`;
  - downgrade then upgrade works.
- [x] T005 [P] Unit tests `api/tests/unit/test_sas_row.py`, cases inline:
  - Header matching (research R2, R3): case and spaces; `username`/`phone` missing named; `ct_password`, `CT_Password`
    and any `*password*` header never mapped; unknown headers ignored.
  - Username (R4): trimmed; key upper-cased with Latin digits; empty → `username_missing`.
  - Split: `ALM03-07801234567` → prefix `ALM03`, phone `07801234567`. `RBD-01S-7801234567` → prefix `RBD-01S`, phone
    `07801234567`. `abc` → no phone, no prefix.
  - Tower code from prefix: dashes and spaces removed, upper-cased.
  - Phones (R5): column via §8.1 or None, written value kept.
  - Dates (R6): xlsx datetime, `YYYY-MM-DD`, `YYYY/MM/DD HH:MM:SS` read as Baghdad and returned UTC; `0000-00-00…` →
    None without the unreadable mark; garbage → None with it.
  - Names: trimmed and collapsed; full name of the non-empty two.
  - Diff (R7): `new` / `unchanged` / `update` with the changed field names.
  - Flags (R9): `username_dup_file` with the other rows; `phone_in_sijil` for new rows and for updates whose phones
    changed only, ignoring a request with the same upper-case username; the informational codes;
    `allowed_choices`.
- [x] T006 [P] Extend `api/tests/unit/test_legacy_file.py`: `read_table(data, max_bytes=…, max_rows=…)` honours the
  given limits; the defaults stay 5 MB and 2 000.

### Implementation

- [x] T007 Write migration `api/migrations/versions/0018_sas_import.py` for every table, column, check, index and FK
  of data-model.md, in particular: data-model.md `sas_subscribers.username_key` (unique),
  `sas_subscribers.phone` and `sas_subscribers.username_phone` (format checks, indexed), `sas_subscribers.tower_id`
  and `sas_tower_mappings.tower_id` (FK `ON DELETE RESTRICT`), `sas_tower_mappings.prefix` (PK),
  `sas_imports.file_name`, `sas_import_previews.expires_at`.
- [x] T008 Add the models `SasImport`, `SasSubscriber`, `SasSubscriberChange`, `SasTowerMapping` and
  `SasImportPreview` in `api/app/models/sas.py`, with columns as in data-model.md, and export them from
  `api/app/models/__init__.py`. Then run T004 green.
- [x] T009 [P] Give `read_table` in `api/app/services/legacy_file.py` the keyword limits `max_bytes` and `max_rows`
  (the defaults stay as they are), and add `SAS_MAX_FILE_BYTES = 15 MB` and `SAS_MAX_ROWS = 50 000`. Then run T006
  green.
- [x] T010 Implement `api/app/core/sas_row.py` (no database access):
  - `match_headers`, which never maps a password column (R3);
  - `clean_row(index, raw)`, giving data-model.md `SasPreviewRow` keys without `kind`/`flags`;
  - `split_username`, `tower_code_from_prefix`, `parse_sas_date`;
  - `COMPARED_FIELDS` and `diff(stored, row)`;
  - an `Existing` dataclass: stored rows by key, Sijil phones → [(request label, upper username)], legacy phones;
  - `compute_flags(rows, existing)`, `allowed_choices`.
  Then run T005 green.
- [x] T011 [P] In `api/tests/fixtures/sas/`, write `sas_sample.csv` with about 20 synthetic rows covering every
  quickstart case, with `SYNTH-PW-<n>` in each `ct_password` cell. Write `sas_sample_2.csv` (one row added, one
  phone and expiry changed, one row removed). Add `expected.json` with the expected counts, flags and prefixes, and a
  helper `api/tests/helpers/sas.py` that builds the same rows as `.xlsx` with openpyxl and seeds the towers `ALM03`,
  `KZF06`, `RBD01S` and `SMR01`.
- [x] T012 Run the whole api suite green (the legacy tests included, after T003 and T009).
- [x] T013 Batch 1 report: red then green for T004–T006. **Batch 1 commit.**

**Checkpoint**: the tables and the pure rules are ready.

---

## Phase 3: User Story 1 — The admin imports the SAS file after a preview (P1) 🎯 MVP

**Goal**: upload → preview (counts, mapping table, flagged groups) → choices → all-or-nothing confirm → summary.
`ct_password` is never kept.

**Independent Test**: spec US1 Independent Test, using `sas_sample.csv`.

### Tests for the preview (write first, run red)

- [x] T014 [P] [US1] Integration tests `api/tests/integration/test_sas_preview.py`:
  - access: anyone without `reports` gets 403 on every `/admin/imports/sas` route, and another admin's preview is 404;
  - refusals: a file without `username` → 422 `import_columns_missing` naming it; too large → 413; too many rows and
    unreadable → 422;
  - `sas_sample.csv` and its `.xlsx`: counts, prefixes and flagged rows match `expected.json`;
  - no `sas_subscribers` row exists after the upload;
  - a saved `sas_tower_mappings` prefix comes pre-filled with `from_previous`;
  - a second upload replaces the first preview;
  - an expired preview → 404 and is swept;
  - `phone_in_sijil` lists only pending, approved and linked live requests (rejected and deleted never count).
- [x] T015 [P] [US1] Integration test `api/tests/integration/test_sas_password_never_kept.py` (preview part). Upload the
  csv and the xlsx, then search the response bodies, the `sas_import_previews` rows (as text) and the captured log
  output (caplog plus the access log) for every `SYNTH-PW-` marker. None may be found (SC-003).

### Implementation

- [x] T016 [US1] In `api/app/services/sas_import_service.py`, write `load_existing(db, rows)`. It reads the stored SAS
  rows by `username_key`, the active live Sijil requests whose phone is in either phone set (with label and
  upper-case username), and the legacy phones that count. The `IN` lists are chunked by 1 000.
- [x] T017 [US1] In the same module, write `create_preview(db, user, file_name, data)`:
  - read with the SAS limits and map the headers (`import_columns_missing` names the missing ones);
  - clean the rows and resolve towers by the rule, then by saved mapping, else list the prefix;
  - compute the kind, flags and info, and the `missing_ids`;
  - sweep expired previews and replace the user's previous one;
  - save `sas_import_previews` (data-model.md).
  Also write `get_preview`, `cancel`, `sweep_expired`, and a `summary(preview)` that builds the `SasPreview`
  contract. Log the preview id and counts only (research R11).
- [x] T018 [US1] Write `api/app/schemas/sas_import.py`: `SasPreview`, `SasChoicesIn` and `SasImportSummary`, as in
  contracts/api.md.
- [x] T019 [US1] Add a second router for `/admin/imports/sas` in `api/app/api/admin_imports.py` with POST, GET and
  DELETE previews, guarded by `reports`. Read the upload capped at `SAS_MAX_FILE_BYTES`, register the router in
  `api/app/main.py`, and add the SAS sweep to the startup sweep.
- [x] T020 [US1] Make sure the upload route is excluded from body and URL logging, as the 014 import routes are, and
  that error messages never echo cell values. Then run T014 and T015 green.
- [x] T021 [US1] Batch 2 report. **Batch 2 commit.**

### Tests for choices and confirm (write first, run red)

- [x] T022 [P] [US1] Integration tests `api/tests/integration/test_sas_confirm.py`:
  - choices: `import` on `username_missing` → 422 `choice_not_allowed`; two `import` on one repeated username → 422;
    a prefix with an unknown tower → 422 `tower_not_found`; `tower_id: null` is accepted («بلا برج»);
  - refusals: confirming with a choice or a prefix waiting → 409 `preview_choices_missing` listing both;
  - a confirm saves, in one transaction:
    - the chosen rows with every data-model.md `sas_subscribers` column (`first_import_id` and `last_import_id`,
      tower from the rule or the mapping);
    - the `sas_tower_mappings` rows (`set_by`, `import_id`);
    - one `sas_imports` row;
    - one `sas.imported` audit line whose `after` holds counts and file name only (no username, phone or name);
  - the summary lists skipped rows by index and SAS id only;
  - an injected failure mid-way leaves no `sas_*` row (SC-007);
  - `preview_changed` when a Sijil request takes a row's phone between preview and confirm;
  - a SAS confirm waits on the lock while a legacy confirm holds it.
- [x] T023 [P] [US1] Extend `test_sas_password_never_kept.py` to the confirm. After the confirm, check every `sas_*`
  table and `audit_log` (as text), the summary and the logs: no marker anywhere.
- [x] T024 [P] [US1] Vitest `web/src/__tests__/sasImport.test.tsx` (mocked API):
  - an upload shows the counts and the mapping table;
  - a tower select (with «بلا برج») sends `prefixes`;
  - «تخطي للكل» sets «تخطي» on the group's rows, and one row can then be set back to «استيراد»;
  - confirm stays disabled while choices or prefixes are waiting;
  - the confirm dialog shows, then the summary;
  - `preview_changed` reloads the rows that need a choice;
  - Arabic error messages appear for each import error code.

### Implementation

- [x] T025 [US1] In `sas_import_service.py`, write `set_choices` (rows and prefixes, partial updates, validation as
  in R9).
- [x] T026 [US1] Write `confirm`:
  - take the shared lock and re-validate (research R12);
  - insert the `new` rows and update the `update` rows in batches of 1 000, writing one data-model.md
    `sas_subscriber_changes` row (`before`, `after` of the changed fields) per update;
  - save the mappings;
  - write `sas_imports`, then the audit line (research R10);
  - delete the preview and commit; on any failure, roll back.
  Leave the missing marking to T049. Add the confirm and choices routes. Then run T022 and T023 green.
- [x] T027 [US1] Write `web/src/lib/sasImport.ts`: API calls, flag and info labels in Arabic («بلا يوزر», «يوزر مكرر
  في الملف», «الهاتف في طلب سِجلّ», «نفس اليوزر في سِجلّ», «بلا هاتف صالح», «يوزر بلا هاتف», «تاريخ غير مقروء»,
  «هاتف مكرر في الملف», «الهاتف عند مشترك قديم», «غير موجود في آخر ملف», «سيُحدَّث», «جديد», «بلا تغيير»), and error
  messages.
- [x] T028 [US1] Write `web/src/pages/admin/import/SasImport.tsx` (research R16). It shows the counts, the mapping
  table (prefix, rows, tower select with «بلا برج», «من استيراد سابق»), the flagged groups (paged above 200 rows)
  with «استيراد» / «تخطي» and «تخطي للكل», «تأكيد الاستيراد» with a dialog, and the summary. It must work at phone
  width.
- [x] T029 [US1] In `web/src/pages/admin/import/ImportPage.tsx`, the SAS tab renders `SasImport` in place of
  «قريباً». Add the audit label `'sas.imported': 'استيراد مشتركي SAS'` and its count labels to
  `web/src/lib/labels.ts`. Then run T024 green.
- [x] T030 [US1] Run the US1 tests and both whole suites green.
- [x] T031 [US1] Batch 3 report. **Batch 3 commit.**

**Checkpoint**: the SAS file can be imported. MVP.

---

## Phase 4: User Story 2 — The check engine knows the SAS subscribers (P1)

**Goal**: both phones of a SAS subscriber give case 1 in the early, submit and re-check paths; a return keeps the SAS
username; nothing reaches the marketer.

**Independent Test**: spec US2 Independent Test.

### Tests (write first, run red)

- [ ] T032 [P] [US2] Integration tests `api/tests/integration/test_sas_source.py`:
  - `find_matches` returns a `sas` record for the phone column and for the username phone, one record when both
    are equal, and none for a skipped row or for a NULL key;
  - the record never sets `national_id`, `family` or `pending`;
  - a row with `missing_since` set still matches.
- [ ] T033 [P] [US2] Integration tests in `api/tests/integration/test_sas_check_flow.py`:
  - the OTP precheck refuses a SAS phone (`phone_used`);
  - a submit with a SAS phone as a new request is refused and the draft stays;
  - a return by a SAS phone writes `matched_source = 'sas'`; when accepted it keeps the SAS username as written;
    with a Sijil target that has a username, the Sijil one wins (research R14);
  - the 010 re-check after a pin sees SAS records;
  - the marketer responses for all of the above contain no SAS field (the username, name and tower strings are
    searched in the bodies).

### Implementation

- [ ] T034 [US2] Write `api/app/services/sas_source.py`, registering `sas` through `match_service.register_source`
  (research R8). Import it in `api/app/main.py`. Then run T032 green.
- [ ] T035 [US2] In `api/app/services/submit_service.py`, `_username` falls back to the SAS username: newest
  `last_import_id`, then highest id (research R14). Update its docstring.
- [ ] T036 [US2] Run T033 green.
- [ ] T037 [US2] Run the whole api suite green. **Batch 4 commit.**

---

## Phase 5: User Story 3 — The admin sees the SAS record in the review file (P2)

**Goal**: the linked record «مشترك SAS» with username, name, phones, tower, dates and expiry «حسب آخر استيراد».

**Independent Test**: spec US3 Independent Test.

### Tests (write first, run red)

- [ ] T038 [P] [US3] Integration tests `api/tests/integration/test_sas_linked_record.py`:
  - the review file of a pending return linked to a SAS row has `source = "sas"` and the fields of contracts/api.md;
  - `expiry_as_of` is the date of the last import that wrote the row;
  - `username_phone` appears only when it differs;
  - `missing_from_file` is set after a missing mark;
  - the tower name is the current one;
  - there are no notes, `parent_name`, national ID, family number or images;
  - the `sas` resolver returns `available=False` for an unknown ref.
- [ ] T039 [P] [US3] Extend `web/src/__tests__/linkedRecordCard.test.tsx` for a `sas` record: «مشترك SAS», username,
  phone and username phone, «اسم البرج (رمز البرج)» or «بلا برج», «تاريخ الانتهاء … (حسب آخر استيراد …)»,
  «منتهي» for a past expiry, «غير موجود في آخر ملف», and no image area.

### Implementation

- [ ] T040 [US3] In `api/app/services/linked_records.py`, add `expiry_as_of`, `last_online`, `group_name`,
  `username_phone` and `missing_from_file` to `LinkedRecord`, and add the same fields to `LinkedRecordOut` in
  `api/app/schemas/admin_requests.py`.
- [ ] T041 [US3] Register the `sas` resolver in `api/app/services/sas_source.py` (research R13). Then run T038 green.
- [ ] T042 [US3] Add `SOURCE_LABELS.sas = 'مشترك SAS'` to `web/src/lib/labels.ts`, and the SAS fields to
  `web/src/pages/admin/pending/LinkedRecordCard.tsx`. Then run T039 green.

---

## Phase 6: User Story 4 — The SAS import stays out of requests, links and counters (P2)

**Goal**: an import never changes a request, a link, a counter or a notification; there is no delete action; towers
in use are protected.

**Independent Test**: spec US4 Independent Test.

### Tests (write first, run red)

- [ ] T043 [P] [US4] Integration tests `api/tests/integration/test_sas_isolation.py`. Seed approved, linked, unlinked,
  rejected and deleted requests, then import a SAS file holding some of their usernames and phones. Check that:
  - every `requests`, `request_links` and `notifications` row is unchanged;
  - the admin home numbers, «بانتظار الربط», «المربوطة مؤخراً» and the marketer home counter with «و M بلا عمولة»
    are equal before and after;
  - a same-username row is counted `same_username_in_sijil` with no choice;
  - a phone held only by a rejected or deleted request is not flagged;
  - there is no delete route for SAS rows (404/405);
  - «فتح طلب برقمه» with a SAS id → 404;
  - the marketer request search with a SAS username, phone or name finds nothing (FR-020).
- [ ] T044 [P] [US4] Integration test in `api/tests/integration/test_settings_areas_towers.py` (extend): deleting a tower,
  or editing its code, while a SAS subscriber or a mapping uses it → 409 `item_in_use` (research R15).

### Implementation

- [ ] T045 [US4] Register the tower usage check (SAS subscribers or mappings) through
  `settings_service.register_usage_check("tower", …)` in `api/app/services/sas_source.py`. Then run T044 green.
- [ ] T046 [US4] Run T043. It should pass with no code change, because the tables are separate; fix anything that
  leaks.

---

## Phase 7: User Story 5 — The admin re-imports the SAS file (P2)

**Goal**: re-upload updates by username, adds new rows, keeps unchanged rows untouched, marks missing rows, and
reuses mappings.

**Independent Test**: spec US5 Independent Test, using `sas_sample.csv` then `sas_sample_2.csv`.

### Tests (write first, run red)

- [ ] T047 [P] [US5] Integration tests `api/tests/integration/test_sas_reimport.py`:
  - after importing `sas_sample.csv`, the preview of `sas_sample_2.csv` counts 1 new, 1 update, the rest unchanged,
    and 1 missing from file, and does not ask for the prefix mapped the first time;
  - the confirm updates the changed row (`last_import_id`, one `sas_subscriber_changes` row with only the changed
    fields), leaves unchanged rows' `updated_at` as it was, and sets `missing_since` and `missing_import_id` on the
    missing row, counting `missing_marked`;
  - re-importing the first file clears the mark (`missing_cleared`) and does not change `missing_since` on rows that
    are still missing;
  - «تخطي» on an update row leaves the stored row as it is and does not mark it missing;
  - the old phone of the updated row no longer matches and the new one does (US2 scenario 6);
  - the missing row still matches.
- [ ] T048 [P] [US5] Extend `sasImport.test.tsx`: the counts show «سيُحدَّث» and «غير موجود في آخر ملف», and a
  pre-filled mapping shows «من استيراد سابق» and can be changed.

### Implementation

- [ ] T049 [US5] In `confirm` (`sas_import_service.py`), set data-model.md `sas_subscribers.missing_since` and
  `sas_subscribers.missing_import_id` for the preview's `missing_ids` (re-checked at confirm) when they are NULL, and
  clear them on rows the file holds. Count `missing_marked` and `missing_cleared` in `sas_imports` and in the audit.
  Then run T047 green.
- [ ] T050 [US5] Adjust `SasImport.tsx` for the re-import counts. Then run T048 green.
- [ ] T051 Run the US3–US5 tests and both whole suites green. **Batch 5 commit.**

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T052 [P] Playwright `e2e/tests/sas-import.spec.ts`:
  - the `reports` admin uploads the synthetic file, maps the prefix, uses «تخطي للكل», and confirms;
  - the marketer gets case 1 on a SAS phone and on a username phone;
  - the return is accepted with the SAS username;
  - the review admin sees «مشترك SAS» with the expiry;
  - the re-import shows the update and missing counts.
- [ ] T053 [P] Performance check `api/tests/integration/test_sas_volume.py` (marked `slow`). With a generated
  synthetic file of 20 000 rows, the preview and the confirm each finish in under 30 s on the test database (plan
  Performance Goals), and a second confirm of the same file writes no change rows.
- [ ] T054 Grep the new code for log calls and audit payloads, and check that none passes a username, phone, name,
  file cell or the file name to `log.*` (research R11).
- [ ] T055 [P] Write `specs/015-sas-import/manual-test-ar.md`: the manual steps in Arabic, from quickstart.md, using
  the synthetic files only.
- [ ] T056 Run every suite (api, web, e2e). Run the app with `docker compose up` and walk through quickstart.md.
- [ ] T057 Update `docs/system.md` only if the implementation found a rule gap, and stop to ask the owner first.
- [ ] T058 Mark the tasks done and set the spec status to Implemented. **Batch 6 commit.**

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 (Phases 3a, 3b).
- US2 needs only Phase 2 plus confirmed rows (it can use direct inserts in tests), so it can follow US1 or run beside
  it.
- US3 needs US2's `sas_source.py`. US4 needs US1's confirm. US5 needs US1's confirm (T026).
- Polish comes last.
- Within each phase: tests red → models/services → routes → web → green.

## Parallel Examples

- Batch 1: T004, T005, T006 and T011 together; then T007→T008, alongside T009 and T010.
- US1: T014 with T015; T022, T023 and T024 together.
- Batch 5: T038, T039, T043, T044, T047 and T048 are all independent test files.

## Implementation Strategy

- MVP = batches 1–3 (the import itself). Batch 4 brings the anti-fraud value, and should follow immediately.
- Each batch ends green and with a commit. The batch reports list red then green for every test task.
