---

description: "Task list for feature 018: Subscriber File and Search"
---

# Tasks: Subscriber File and Search

**Input**: Design documents from `specs/018-subscriber-file-search/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's rule: **each new test is run red before its
code is written**. Report red and green for every test task.

**Test rules**:
- Synthetic data only; no real card images or subscribers (CLAUDE.md). Everything runs on the owner's machine only.
- **No existing file is overwritten**: a new file is created only after checking the path is free; an existing file
  is changed with an edit (append or replace a known part), never rewritten whole.
- Requests from `api/tests/helpers/requests.py::request_factory` (`mark_deleted`, `add_pin`, `link_request`); admins
  from `api/tests/helpers/review.py::admin_with`; legacy rows from `api/tests/helpers/legacy.py::legacy_subscriber`;
  SAS rows from `api/tests/helpers/sas.py::sas_subscriber`; time from `frozen_clock`.
- Vitest runs from PowerShell (project note).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US3 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each ends at a phase boundary and with a commit):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T008 |
| 2 | 3 (US1 search) | T009–T018 |
| 3 | 4 (US2 file) | T019–T028 |
| 4 | 5–6 (US3 marketer, privacy and speed) | T029–T034 |
| 5 | 7 (Polish, e2e, manual test) | T035–T041 |

No migration in this feature (data-model.md).

---

## Phase 1: Setup

- [x] T001 Confirm the baseline: `docker compose up -d`, then `docker compose exec api pytest` and the web suite (from
  PowerShell) are green on the branch before any change; note the counts in the batch report.
- [x] T002 [P] Add error codes with Arabic messages by editing `api/app/errors.py` (contracts/api.md):
  `search_unclear` (422, «اكتب اسماً (3 أحرف على الأقل) أو هاتفاً أو رقماً») and `identity_search_forbidden` (403,
  «البحث بالرقم الوطني أو العائلي يحتاج صلاحية المراجعة»).

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the name folding and the search classifier that every story uses.

### Tests (write first, run red)

- [x] T003 [P] New unit test `api/tests/unit/test_arabic_fold.py`: `fold_arabic` maps أ/إ/آ/ٱ → ا, ة → ه, ى → ي,
  removes diacritics, tatweel and direction marks, collapses spaces; «أحمد» and «احمد» fold the same; None and ""
  give None (research R3).
- [x] T004 [P] New fixture `api/tests/fixtures/subscriber_search_cases.json` and new unit test
  `api/tests/unit/test_subscriber_search.py` driving `classify` (research R2, data-model.md › Derived: search term):
  «1004», «T3C-1004», «#t3c-١٠٠٤» → number; «T3C-001», «t3c-٠٤٢» → legacy_number (checked **before** the request
  number: «T3C-» and exactly 3 digits; request numbers start at 1001, analysis A1); «199012345678», «١٩٩٠١٢٣٤٥٦٧٨» →
  national_id; `0780 123 4567`, `+964 780 123 4567` → phone `07801234567`; «1990 a 1234567890123», «1990O…» →
  family (comparison key); «alm03-07801234567» → username `ALM03-07801234567`; «أحمد علي» → name (folded); «اح» (2
  letters), «%», «_», «abc», «12345» → None; `requires_review` true only for national_id and family.

### Implementation

- [x] T005 Add `fold_arabic` by editing `api/app/core/arabic_name.py` (append; existing functions unchanged); T003
  green.
- [x] T006 New module `api/app/core/subscriber_search.py` (`Term`, `classify`, `MIN_NAME_LETTERS = 3`) reusing
  `request_number.parse`, `normalize_phone`, `family_key`, `national_id` normalization and `clean_arabic_name`;
  T004 green.
- [x] T007 [P] Add labels by editing `web/src/lib/labels.ts` (append): `SUBSCRIBER_SOURCE_LABELS` («طلب سِجلّ»،
  «مشترك قديم»، «مشترك SAS»), `LINK_REASON_LABELS` («نفس الشخص»، «نفس الهاتف»، «نفس العائلة»),
  `HISTORY_KIND_LABELS` (أُرسل، قُبل، رُفض، تثبيت رقم، تم الربط، تراجع عن الربط، حُذف), with a Vitest case in a new
  file `web/src/__tests__/subscriberLabels.test.ts`.
- [x] T008 [P] New file `web/src/lib/subscribers.ts`: types of contracts/api.md and the two calls (`searchSubscribers`,
  `getSubscriberFile`).

**Checkpoint**: batch 1 commit (with the plan files).

---

## Phase 3: User Story 1 — The admin finds a subscriber (Priority: P1) 🎯 MVP

**Goal**: one search across the three sources, per permission.

**Independent Test**: spec US1.

### Tests (write first, run red)

- [x] T009 [P] [US1] New integration test `api/tests/integration/test_subscriber_search_api.py`: each kind across the
  sources (phone finds a request, a legacy row and a SAS row by its column phone and by its username phone; family
  finds request and legacy; username finds request and SAS; name with swapped أ/ا and ة/ه finds all three; legacy
  number; request number), rejected requests and «ملغي» legacy rows are found, rows have the result-row keys of
  data-model.md › Derived: result row, newest first, `limit` 50 and `total`, `search_unclear` for «اح».
- [x] T010 [P] [US1] In the same file: a deleted request is not found by phone or name and is found by number as
  `{deleted: true, number_label}` with every other field null (FR-006).
- [x] T011 [P] [US1] In the same file: as `link`-only and `reports`-only admins, national-ID and family searches
  answer `403 identity_search_forbidden` for an existing and a made-up number alike, and no lookup runs (counted with
  a SQL event listener); as main admin and `review` they work; as `settings`-only and marketer every search is
  `403 forbidden` (FR-001, FR-009).
- [x] T012 [P] [US1] New Vitest `web/src/__tests__/subscriberSearch.test.tsx`: typing and searching calls
  `searchSubscribers`; rows show source label, name, tower, phone, status (request status chip in its §7.2 color,
  legacy status text, SAS «حسب آخر استيراد»), date; «سجل محذوف» row; the two Arabic refusals; paging «التالي».

### Implementation

- [x] T013 [US1] New `api/app/services/subscriber_search.py`: one capped query per source (research R4), folded-name
  SQL (research R3), merge newest first, paging, deleted only for `number` (research R6).
- [x] T014 [US1] New `api/app/schemas/subscribers.py` (`ResultRow`, `SearchOut`).
- [x] T015 [US1] New router `api/app/api/admin_subscribers.py` with `GET /api/admin/subscribers`
  (`require_permission("review", "link", "reports")`), the identity-kind check before the service call, included by
  editing `api/app/main.py`; T009–T011 green.
- [x] T016 [P] [US1] New page `web/src/pages/admin/subscribers/SubscriberSearch.tsx`.
- [x] T017 [US1] Route `/admin/subscribers` to the new page by editing `web/src/router.tsx`, and remove
  `AdminSubscribers` by editing `web/src/pages/admin/placeholders.tsx`; T012 green.
- [x] T018 [US1] Logs: the search logs its kind and result count only (no query text); a test in
  `api/tests/integration/test_subscriber_search_api.py` with `caplog` proves no phone, name or number appears.

**Checkpoint**: batch 2 commit.

---

## Phase 4: User Story 2 — The admin reads the subscriber's file (Priority: P1)

**Goal**: the read-only file of one record with its linked records and history.

**Independent Test**: spec US2.

### Tests (write first, run red)

- [x] T019 [P] [US2] New integration test `api/tests/integration/test_subscriber_file.py` (research R5): a request
  with an older rejected request of the same person («نفس الشخص»), a SAS row with its phone («نفس الهاتف»), a legacy
  row with its family number («نفس العائلة»), and a «ملغي» legacy row with its phone: all listed with their reasons;
  a record found by two reasons shows the strongest; more than 50 linked → 50 and `more_linked`; the file of a SAS
  row lists the request by phone; the file of a legacy row lists the request by family; 404 for an unknown record.
- [x] T020 [P] [US2] In the same file: history (research R9) of a request with submitted, accepted by an admin, a pin,
  a link, an undo with its reason, in time order; an automatic acceptance has `by_name: null`; a rejected request
  shows its reason; the pin line has the field and never the value.
- [x] T021 [P] [US2] In the same file: legacy record fields (`legacy_number`, `status_text`, `extra`, «غير مكتمل»
  when an image is missing); SAS record fields (`expires_at`, `group_name`, `last_online_at`, `missing_since`,
  `username_phone`, `no_documents`); a deleted request's file has the kept fields only and `deleted: true`.
- [x] T022 [P] [US2] New Vitest `web/src/__tests__/subscriberFile.test.tsx`: the record header by source, the
  identity block and images only when present in the response, linked records with reason labels opening their own
  file, the history lines, «غير مكتمل», «بلا مستمسكات في سِجلّ», «غير موجود في آخر ملف», «سجل محذوف», no edit
  control anywhere (FR-010).

### Implementation

- [x] T023 [US2] New `api/app/services/subscriber_file.py`: `build(db, user, source, ref)` (research R5, R6, R9).
- [x] T024 [US2] Add the file schemas (record per source, `LinkedOut`, `HistoryEvent`, `FileOut`) by editing
  `api/app/schemas/subscribers.py`; identity keys added only for entitled callers (research R7).
- [x] T025 [US2] Route `GET /api/admin/subscribers/{source}/{ref}` by editing `api/app/api/admin_subscribers.py`;
  T019–T021 green.
- [x] T026 [P] [US2] New page `web/src/pages/admin/subscribers/SubscriberFile.tsx` (images through the existing
  `/api/admin/request-images/{id}` and `/api/admin/legacy-images/{id}` blob routes).
- [x] T027 [US2] Route `/admin/subscribers/:source/:ref` by editing `web/src/router.tsx`, and rows of the search page
  link to it; T022 green.
- [x] T028 [US2] Image log check in `api/tests/integration/test_subscriber_file.py`: as `review`, opening an image id
  from the file through the existing routes writes an `image_access_log` row with `request_id` or
  `legacy_subscriber_id` (FR-011).

**Checkpoint**: batch 3 commit.

---

## Phase 5: User Story 3 — The marketer stays within their own requests (Priority: P1)

- [ ] T029 [P] [US3] New integration test `api/tests/integration/test_subscriber_privacy.py`: as a marketer, both new
  routes answer 403; the marketer's existing own search (`GET /api/requests?q=`) returns nothing for a phone that
  belongs to a SAS row and to another marketer's request (FR-002, US3).

## Phase 6: Privacy and speed (cross-story)

- [ ] T030 [P] In `api/tests/integration/test_subscriber_privacy.py`: for `link`-only and `reports`-only admins, the
  key sets of every result row and every file (record and linked rows, all three sources) contain no
  `national_id`, `family_number`, `card_fields` or `images`, and the pin history lines have no `field`; for `review`
  they are present (FR-009, SC-004).
- [ ] T031 [P] In the same file: PUT, PATCH, POST and DELETE on both routes answer 405 (FR-010); file logs carry
  `source:ref` only (FR-012).
- [ ] T032 [P] New `api/tests/integration/test_subscriber_performance.py`: 20,000 SAS, 500 legacy, 5,000 requests
  inserted in bulk; a phone search, a name search and a family search each return their first page in under 1 s, and
  a file with 20 linked records opens in under 1 s (SC-001, SC-002).
- [ ] T033 If T032 fails, add the smallest index that makes it pass (a migration only then), and record it in
  research.md R3.
- [ ] T034 Run the full suites (api, web); fix only what this feature broke.

**Checkpoint**: batch 4 commit.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T035 [P] New `api/tests/e2e_subscriber_seed.py` (synthetic: a request, a legacy row with its family number, a
  SAS row with its phone, a deleted request; admins with `review` and with `link`), run by editing
  `scripts/e2e.sh` (append one line after the 017 seed).
- [ ] T036 [P] New e2e `e2e/tests/subscriber-file.spec.ts` (local Docker only): `review` admin searches by phone,
  opens the file, sees the linked records and an image; `link` admin sees no identity data and is refused a
  national-ID search; the deleted request is found by number only.
- [ ] T037 Run the whole suite: pytest, Vitest (PowerShell) and the full Playwright run (`bash scripts/e2e.sh`); all
  green; note counts.
- [ ] T038 `docker compose up` on the owner's machine: the app starts, head stays `0020` (or the T033 migration).
- [ ] T039 New `specs/018-subscriber-file-search/manual-test-ar.md`: Arabic manual steps for the owner, local only.
- [ ] T040 Check `docs/system.md` 1.24 §10 item 4 against what was built; edit it only where the build differs and
  tell the owner.
- [ ] T041 Mark the tasks done; batch 5 commit.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US2 (the file page is reached from the search). US3 and Phase 6 need US1 and US2.
- Within a story: tests (red) → service → schema/route → web.

## Parallel Examples

- Phase 2: T003, T004 together; T007, T008 beside T005/T006.
- US1: T009–T012 together; T016 beside T013–T015.
- US2: T019–T022 together; T026 beside T023–T025.

## Implementation Strategy

- MVP = batches 1–2: the admin can search all sources with the right permissions.
- Batch 3 adds the file; batch 4 the privacy and speed checks; batch 5 the e2e and the manual test.
- Each batch ends with green suites, a commit and Arabic manual steps. Everything runs on the owner's machine only.
