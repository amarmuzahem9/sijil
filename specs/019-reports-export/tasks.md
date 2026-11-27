---

description: "Task list for feature 019: Reports and Export"
---

# Tasks: Reports and Export

**Input**: Design documents from `specs/019-reports-export/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's rule: **each new test is run red before its
code is written**. Report red and green for every test task.

**Test rules**:
- Synthetic data only; no real card images or subscribers (CLAUDE.md). Everything runs on the owner's machine only.
- **No existing file is overwritten**: a new file is created with the Write tool only after checking the path is
  free; an existing file is changed with an edit (append or replace a known part), never rewritten whole.
- Requests from `api/tests/helpers/requests.py::request_factory` (`link_request`, `pay_month`, `add_images`,
  `mark_deleted`); admins from `api/tests/helpers/review.py::admin_with` and `headers_for`; synthetic JPEGs from
  `api/tests/helpers/card_images.py::scenario_jpeg`; time from `frozen_clock`.
- Vitest runs from PowerShell (project note).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each ends at a phase boundary and with a commit):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T010 |
| 2 | 3 (US1 report) | T011–T020 |
| 3 | 4 (US2 export) | T021–T033 |
| 4 | 5–6 (US3 commissions, US4 marketer, privacy and speed) | T034–T043 |
| 5 | 7 (Polish, e2e, manual test) | T044–T050 |

---

## Phase 1: Setup

- [x] T001 Confirm the baseline: `docker compose up -d`, then `docker compose exec api pytest` and the web suite (from
  PowerShell) are green on the branch before any change; note the counts in the batch report.
- [x] T002 [P] Add error codes with Arabic messages by editing `api/app/errors.py` (contracts/api.md):
  - `period_invalid` (422, «الفترة غير صحيحة»);
  - `no_rows` (422, «لا توجد طلبات بهذه الفلاتر»);
  - `export_too_large` (422, «ضيّق الفلاتر، الحد 5,000 طلب»);
  - `export_in_progress` (409, «عندك تصدير قيد التجهيز»);
  - `identity_export_forbidden` (403, «تصدير الرقم الوطني والعائلي والصور يحتاج صلاحية المراجعة»);
  - `export_not_ready` (409, «الملف غير جاهز»);
  - `export_removed` (410, «انتهت صلاحية الملف، صدّره من جديد»);
  - `ticket_invalid` (403, «رابط التنزيل غير صالح أو منتهي»).
- [x] T003 [P] Add `exports_dir: str = "/data/exports"` by editing `api/app/config.py` (research R10), and an
  `EXPORTS_DIR` comment line by editing `.env.example`; tests point it at `tmp_path` through the existing settings
  override in `api/tests/conftest.py` (edit, append a fixture `exports_dir`).
- [x] T004 [P] Add the `exports` volume by editing `docker-compose.yml`:
  - mount it on `api` only, at `/data/exports`, and declare it under `volumes:`;
  - check every overlay that redefines `api` volumes (`docker-compose.override.yml`, `docker-compose.e2e.yml`,
    `docker-compose.server.yml`, `docker-compose.deploy-e2e.yml`) and edit only those that need it;
  - `backup` and `docker-compose.drill.yml` MUST NOT mount it (R10).

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the period rules and the `exports` table that the report and the export both use.

### Tests (write first, run red)

- [x] T005 [P] New unit test `api/tests/unit/test_report_period.py` for `period_bounds` (research R2):
  - `week` on a Saturday starts that day, and on a Friday starts the Saturday before;
  - `month` starts on the 1st;
  - `range` includes both days: 23:59 Baghdad on `to` is in, 00:00 the next day is out;
  - bounds come back in UTC;
  - `from` > `to` and a missing date for `range` raise `period_invalid`;
  - a range of several years is accepted (no maximum length, analysis M2).
- [x] T006 [P] New integration test `api/tests/integration/test_migration_0021.py` (the project's migration-test naming) for `data-model.md › exports.state`,
  `exports.ready_at`/`exports.expires_at` and the `exports_one_preparing` index:
  - a bad state is refused by the database;
  - `ready` without `ready_at`/`expires_at` is refused;
  - a second `preparing` row for the same requester is refused, while `preparing` rows of two requesters are allowed;
  - `created_at` is required;
  - an `image_access_log` row with `purpose = 'export'` is accepted, and `purpose = 'other'` is refused
    (data-model.md › image_access_log.purpose);
  - the migration head is `0021`.

### Implementation

- [x] T007 New module `api/app/core/report_period.py` (`PeriodKind`, `period_bounds(kind, today, from_, to)`,
  `week_start` = Saturday) on `timeutil` Baghdad helpers; T005 green.
- [x] T008 New migration `api/migrations/versions/0021_exports.py`:
  - the `exports` table with every column and constraint of data-model.md › exports: `exports.id`,
    `exports.requester_id`, `exports.filters`, `exports.include_identity`, `exports.state`, `exports.row_count`,
    `exports.missing_images`, `exports.error_code`, `exports.ticket_hash`, `exports.ticket_expires_at`,
    `exports.created_at`, `exports.ready_at`, `exports.expires_at`, `exports.removed_at`;
  - `exports_one_preparing`, `exports_requester_created`;
  - `requests_submitted_at_idx` (data-model.md › requests);
  - widen `image_access_log_purpose` per data-model.md › image_access_log.purpose;
  - the downgrade drops the table and indexes and restores the purpose check, refusing if `export` access rows
    exist.
- [x] T009 New model `api/app/models/export.py` (`Export`) matching T008, and register it by editing
  `api/app/models/__init__.py`; add the `requests_submitted_at_idx` `Index` by editing `api/app/models/request.py`
  `__table_args__`; T006 green.
- [x] T010 [P] Web labels by editing (append):
  - `web/src/lib/labels.ts`: `EXPORT_STATE_LABELS` («جارٍ التجهيز»، «جاهز»، «فشل التجهيز»، «انتهت صلاحية الملف»),
    `DATE_KIND_LABELS` («تاريخ التقديم»، «تاريخ الربط»), `PERIOD_LABELS` («هذا الأسبوع»، «هذا الشهر»، «مدة محددة»);
  - `web/src/lib/auditFormat.ts`: `requests.exported` «تصدير طلبات» (row count, numbers, «مع الأرقام والصور» or
    not), `export.downloaded` «تنزيل تصدير», `commissions.exported` «تصدير عمولات» (month);
  - extend the existing auditFormat test by editing it.

**Checkpoint**: batch 1 commit (with the plan files).

---

## Phase 3: User Story 1 — The admin filters the requests report (Priority: P1) 🎯 MVP

**Goal**: «التقارير والتصدير» lists the filtered requests with their summaries, per permission.

**Independent Test**: spec US1: October by link date in tower A lists exactly those requests; summaries add up.

### Tests (write first, run red)

- [x] T011 [P] [US1] New `api/tests/integration/test_reports_api.py` covering `GET /api/admin/reports/requests` and
  `/options` (contracts/api.md):
  - the 31 October 23:30 / 2 November case under both date kinds;
  - `week` and `month` with `frozen_clock`;
  - an undone link is absent by link date;
  - every filter alone and combined;
  - a deleted request shows `deleted: true` and `name: null`;
  - 50 per page, newest first by the chosen date, `total` right;
  - each summary adds up to `total`;
  - the archived marketer is in options and keeps their name;
  - a renamed tower shows the stored name.
- [x] T012 [P] [US1] New `api/tests/integration/test_reports_privacy.py`, the report part:
  - main admin and `reports` get 200;
  - `review`-only, `commissions`-only and marketers get 403;
  - the JSON keys of rows and summaries never contain `national_id`, `family_number`, `card_fields`, `birth_date`,
    `images`, `amount`, `rate`, `paid` (R12);
  - `can_export_identity` is true only for the main admin and `reports` + `review`.
- [x] T013 [P] [US1] New `web/src/__tests__/reports.test.tsx`, the report part:
  - the period presets and the range fields;
  - the date-kind switch;
  - filters sent as query parameters;
  - rows with status colors from `requestStatus.ts`, «محذوف» rows without a name;
  - summaries, paging, the empty state «لا توجد طلبات بهذه الفلاتر» with no «تصدير».

### Implementation

- [x] T014 [US1] New `api/app/schemas/reports.py`: `ReportFilters` (query model validating ids, `status`, `type`,
  `date_kind`, period), `ReportRow`, `ReportSummary`, `ReportOut`, `ReportOptions`; allow-list fields only (R12).
- [x] T015 [US1] New `api/app/services/report_service.py` (research R3, R4, R13):
  - `filtered(db, filters)`, the one `select` that the export reuses;
  - `page(...)`, `summaries(...)`, `options(db)`;
  - no identity column selected.
- [x] T016 [US1] New router `api/app/api/admin_reports.py` with `GET /reports/options` and `GET /reports/requests`
  under `require_permission("reports")`, and include it by editing `api/app/main.py`; T011 and T012 green.
- [x] T017 [P] [US1] New `web/src/lib/reports.ts` (types from contracts/api.md, `fetchReport`, `fetchOptions`).
- [x] T018 [US1] New page `web/src/pages/admin/reports/Reports.tsx` (Arabic, RTL, phone width first). Edit
  `web/src/router.tsx` to use it for `reports`, and remove `AdminReports` from `web/src/pages/admin/placeholders.tsx`
  (edit). A row opens `/admin/subscribers/request/<number>` (018 rules). T013 green.
- [x] T019 [US1] Quick local check of SC-001: time the report with summaries on 2,000 synthetic requests. If it takes
  over 0.5 s, look at the query plan and fix the filter before going on. The full 20,000-row check is T041. — 0.03 s on 2,000
  requests with summaries; no change needed.
- [x] T020 [US1] Run the api and web suites; fix only what this batch broke.

**Checkpoint**: batch 2 commit.

---

## Phase 4: User Story 2 — The admin exports the filtered requests (Priority: P1)

**Goal**: a ZIP export with identity data only by opt-in for entitled admins, a one-use download, everything
audited, files removed after 24 h.

**Independent Test**: spec US2: 3 synthetic requests exported by the main admin with the box give 3 rows and 6
images with working links, and one audit entry with the 3 numbers. A `reports`-only admin has no box and no
`cards/`.

### Tests (write first, run red)

- [x] T021 [P] [US2] New unit test `api/tests/unit/test_export_sheet.py` (research R9):
  - `columns(identity=False)` holds the FR-007 headers and none of the identity headers;
  - `columns(True)` adds them and the two image columns;
  - the workbook is right-to-left;
  - a name «=1+1», «+964…», «-x», «@a» reads back as text (no cell of type `f`);
  - a deleted row has kept fields and «محذوف» only;
  - image cells link to `cards/T3C-<n>-front.jpg`, and a missing image reads «الصورة غير متوفرة»;
  - dates are in Baghdad time and money is an integer.
- [x] T022 [P] [US2] New `api/tests/integration/test_exports_api.py` (contracts/api.md, research R5–R8):
  - lifecycle `preparing` → `ready` with `submit` run inline;
  - `no_rows`, `export_too_large` (5,001), `export_in_progress`;
  - `identity_export_forbidden` for a `reports`-only admin;
  - the list and get show own exports only, and another admin gets 404;
  - the ticket gives a ZIP with `requests.xlsx` and, for identity, `cards/` named by number;
  - the second use of a ticket, a ticket after 60 s, and a ticket used by another admin's id are refused;
  - `review` removed before the ticket or the download refuses and sets `removed`;
  - an image erased after the build (`mark_deleted`) is not in the ZIP;
  - audit rows `requests.exported` (filters, row_count, numbers, identity, missing_images) and `export.downloaded`
    (images);
  - a failed build writes no `requests.exported` row (analysis M1);
  - a download writes exactly one `image_access_log` row with `purpose = 'export'` per image in the ZIP (user, image,
    request, side); a non-identity download and a skipped erased image write none (analysis C1);
  - no audit row holds a synthetic name, phone or national ID;
  - the job re-checks the permissions;
  - `sweep_at_startup` turns `preparing` into `failed`.
- [x] T023 [P] [US2] New `api/tests/integration/test_exports_sweep.py` (R10): with `frozen_clock`:
  - a ready export at 24 h + 1 s is `removed` and its folder is gone;
  - a `failed` export's folder is gone;
  - an export at 23 h stays;
  - `backup.snapshot.stored_files` never lists anything from `EXPORTS_DIR`.
- [x] T024 [P] [US2] Extend `web/src/__tests__/reports.test.tsx` (edit) with the export part:
  - the box shows only when `can_export_identity`;
  - «تصدير» posts the filters and the box;
  - the list moves from «جارٍ التجهيز» to «تنزيل»;
  - «تنزيل» asks for a ticket and navigates to its URL;
  - the errors show their Arabic messages.

### Implementation

- [x] T025 [US2] New `api/app/services/export_sheet.py`: `columns(identity)`, `request_workbook(rows, identity,
  images)` returning bytes. It uses openpyxl with string cells forced to type `s` with the quote-prefix style, RTL
  and a frozen header; T021 green.
- [x] T026 [US2] New `api/app/services/export_service.py`, part 1:
  - `can_export_identity(user)`;
  - `create(db, user, filters, include_identity)` checks the limit and the one-preparing rule against data-model.md ›
    exports.state;
  - the thread pool with a replaceable `submit`;
  - `run(export_id)` re-checks, re-filters via `report_service.filtered`, and writes `requests.xlsx` and
    `manifest.json` into `EXPORTS_DIR/<id>/`. It then sets `ready` with `exports.expires_at` = ready + 24 h and
    records `requests.exported` in the same transaction;
  - a failure sets `failed` with `exports.error_code` and removes the folder;
  - `sweep_at_startup`.
- [x] T027 [US2] `export_service.py`, part 2 (edit):
  - `issue_ticket` (32 random bytes; SHA-256 into `exports.ticket_hash`; `exports.ticket_expires_at` = now + 60 s);
  - `open_download` (single use, permission re-check; then, in one transaction before streaming, the
    `export.downloaded` audit with the image count and one `image_access_log` row per image to send, with
    data-model.md › image_access_log.purpose = `export`);
  - `stream_zip` (zipfile over an unseekable writer, ZIP64, stored JPEGs from `UPLOADS_DIR` through
    `image_store.open_path`, an erased image skipped).
- [x] T028 [US2] `export_service.sweep_expired()` (edit), which sets `state = 'removed'` and data-model.md ›
  exports.removed_at, and deletes the folder. Wire it into the lifespan by editing `api/app/main.py`:
  - `sweep_at_startup` and `sweep_expired` run at startup;
  - a 15-minute asyncio task runs `sweep_expired` (not in `test`);
  - `sweep_expired` also runs at the start of every exports route;
  - T023 green.
- [x] T029 [US2] Add the export routes by editing `api/app/api/admin_reports.py`: `POST /exports`, `GET /exports`,
  `GET /exports/{id}`, `POST /exports/{id}/ticket` under `require_permission("reports")`, and `GET
  /exports/{id}/download` with the ticket only (`StreamingResponse`, `Cache-Control: no-store`, attachment name);
  T022 green.
- [x] T030 [P] [US2] Export calls by editing `web/src/lib/reports.ts`: `createExport`, `listExports`, `getExport`,
  `downloadTicket`.
- [x] T031 [US2] New `web/src/pages/admin/reports/ExportsList.tsx`; wire «تصدير», the box and the list into
  `Reports.tsx` (edit). The list polls every few seconds while an export is preparing, and «تنزيل» navigates to the
  ticket URL (native download, no blob). T024 green.
- [x] T032 [US2] Confirm locally with `docker compose up` that the `exports` volume is mounted on `api` only
  (`docker compose config`), and that a download streams on the stack.
- [x] T033 [US2] Run the api and web suites; fix only what this batch broke.

**Checkpoint**: batch 3 commit.

---

## Phase 5: User Story 3 — The commission report is exported with its locked figures (Priority: P2)

**Goal**: «تصدير» on «العمولات» gives a sheet equal to the page.

**Independent Test**: spec US3: after a tier change, the sheets for a paid and an unpaid month equal «العمولات».

### Tests (write first, run red)

- [x] T034 [P] [US3] New `api/tests/integration/test_commission_export.py` (research R11):
  - set up a paid October and an unpaid November with `pay_month`, then change the tiers;
  - each cell of «العمولات» equals `GET /api/admin/commissions` for that month, and «الطلبات» equals the detail
    lists (counted, «بلا عمولة», «مدفوع سابقاً» with month);
  - an undo after payment keeps the paid figures with its «تراجع بعد الدفع» note;
  - an archived marketer keeps their row;
  - no phone, national ID or family number appears in either sheet;
  - an `commissions.exported` audit row is written;
  - `reports`-only and marketers get 403, and a bad or future month gives `validation_error` (the 017 error).
- [x] T035 [P] [US3] New `web/src/__tests__/commissionsExport.test.tsx`: the «تصدير» button on `Commissions.tsx`
  calls the export for the chosen month and saves the file.

### Implementation

- [x] T036 [US3] Add `commission_workbook(rows, details)` by editing `api/app/services/export_sheet.py`: the two
  sheets of contracts/api.md, RTL, text cells forced to `s`.
- [x] T037 [US3] Add `GET /export` by editing `api/app/api/admin_commissions.py`, built from
  `commission_service.report` and `detail`, with an `commissions.exported` audit row; T034 green.
- [x] T038 [US3] Add `exportMonth` by editing `web/src/lib/commissions.ts` (`apiFetchBlob`) and the button by editing
  `web/src/pages/admin/commissions/Commissions.tsx`; T035 green.

---

## Phase 6: User Story 4 — The marketer has no export, plus privacy and speed (cross-story)

- [x] T039 [P] [US4] In `api/tests/integration/test_reports_privacy.py` (edit):
  - a marketer gets 403 on every report, export, ticket and commission-export route, including a ticket request for a
    real export id of an admin;
  - a download URL with a valid ticket opened while signed in as a marketer still serves only that ticket's export,
    and only once (the ticket, not the session, decides);
  - the marketer app has no export entry: new `web/src/__tests__/marketerNoExport.test.tsx` renders the marketer
    navigation (phone and large screen) and finds no «تصدير».
  - Built behavior already (batch 3), so each test was proven able to fail by a temporary change in the code
    (marketer let through, ticket not spent, identity columns always on, an «تصدير» entry in the marketer nav):
    red under each change, green once the files were restored byte for byte.
- [x] T040 [P] In `api/tests/integration/test_reports_privacy.py` (edit), the sheet headers of a non-identity export
  never include an identity header, whoever asked (main admin without the box included) (SC-003).
- [x] T041 [P] New `api/tests/integration/test_report_performance.py` (`slow` marker):
  - insert 20,000 synthetic requests in bulk;
  - the report with summaries answers in under 2 s (SC-001);
  - an export of 1,000 requests with synthetic images is ready in under 2 minutes, and a report call made meanwhile
    still answers in under 2 s (SC-002).
- [x] T042 If T041 fails, add the smallest index or query change that makes it pass, and record it in research.md R3.
  — Not needed. On the owner's machine: report over 20,000 requests 0.057 s; export of 1,000 with images ready in
  0.74 s, the report meanwhile at most 0.157 s; the ZIP of 2,001 files streamed in 0.41 s.
- [x] T043 Run the full suites (api, web); fix only what this feature broke.

**Checkpoint**: batch 4 commit.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T044 [P] New `api/tests/e2e_reports_seed.py`:
  - synthetic requests with synthetic images over two months, one deleted, one named «=x»;
  - admins with `reports` and with `reports` + `review`;
  - run it by editing `scripts/e2e.sh` (append one line after the 018 seed).
- [ ] T045 [P] New e2e `e2e/tests/reports-export.spec.ts` (local Docker only):
  - the main admin filters, exports with the box, downloads, and the test opens the ZIP: the sheet rows, `cards/`
    names and links are right;
  - the `reports`-only admin has no box;
  - the commission export downloads;
  - a marketer is refused.
- [ ] T046 Run the whole suite: pytest, Vitest (PowerShell) and the full Playwright run (`bash scripts/e2e.sh`); all
  green; note counts.
- [ ] T047 `docker compose up` on the owner's machine: the app starts and the head is `0021`.
- [ ] T048 New `specs/019-reports-export/manual-test-ar.md`: Arabic manual steps for the owner, local only.
- [ ] T049 Check `docs/system.md` 1.25 §9, §11 and §13 against what was built; edit them only where the build
  differs, and tell the owner.
- [ ] T050 Mark the tasks done; batch 5 commit.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US2: the export reuses the report filter.
- US3 needs only Phase 1 (errors, audit labels) and can follow US1 or run beside US2.
- Phase 6 needs US1–US3. Phase 7 is last.
- Within a story: tests (red) → schema/service → route → web.

## Parallel Examples

- Phase 1: T002, T003, T004 together.
- Phase 2: T005, T006 together; T010 beside T007–T009.
- US1: T011, T012, T013 together; T017 beside T014–T016.
- US2: T021–T024 together; T030 beside T025–T029.
- US3: T034, T035 together.

## Implementation Strategy

- MVP = batches 1–2: an admin can see the filtered report with the right permissions.
- Batch 3 adds the export, the key risk area, with its guards and audit. Batch 4 adds the commission export, the
  marketer refusal and the speed checks. Batch 5 adds the e2e and the manual test.
- Each batch ends with green suites, a commit and Arabic manual steps. Everything runs on the owner's machine only.
