---

description: "Task list for feature 011: Subscriber Deletion"
---

# Tasks: Subscriber Deletion (Erase a Request's Personal Data)

**Input**: Design documents from `specs/011-subscriber-deletion/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's rule: **each new test is run
red before its code is written**. Report red and green for every test task.

**Test rules**:
- Synthetic data only: the fake card reader, made-up numbers (national ID `199000000001`, family
  number `1234A5678901234567`), test images from `api/tests/helpers/card_images.py`. No real card
  images and no real subscribers (CLAUDE.md).
- OTP uses `FakeOtpSender` / `OTP_FAKE_CODE`.
- Requests come from `api/tests/helpers/requests.py::request_factory` (pending or rejected, with
  image files written to the test uploads directory), or from `api/tests/helpers/submit.py` when the
  reasons must come from the real decision.
- Users come from `make_user`: the main admin, an admin with `review`, an admin with `review` and
  `delete`, an admin with `delete` only, and a marketer.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each ends at a phase boundary and with a commit):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T014 |
| 2 | 3 (US1 delete from the file) | T015–T030 |
| 3 | 4–5 (US2 keys freed, US3 permission) | T031–T040 |
| 4 | 6–7 (US4 «سجل محذوف» and counts, US6 open by number) | T041–T053 |
| 5 | 8–9 (US5 marketer view, Polish) | T054–T066 |

---

## Phase 1: Setup

- [x] T001 Add the error codes of [contracts/api.md](./contracts/api.md) to `api/app/errors.py`, with
  their Arabic messages and statuses:
  - 409 `request_deleted` «تم حذف هذا الطلب مسبقاً»;
  - 409 `request_not_deletable` «لا يمكن حذف طلب مقبول أو مربوط»;
  - 422 `number_mismatch` «رقم الطلب غير مطابق».

  For «لا يوجد طلب بهذا الرقم», reuse `request_not_found` and give it a message for the by-number
  lookup.
- [x] T002 [P] Test admins with `delete`. No seed change: `api/app/cli.py::seed_demo` creates only
  marketers. Admins come from `make_user` plus `permissions=[...]` in pytest, and from
  `e2e/tests/helpers.ts::apiCreateReadyAccount({permissions})` in e2e. Both already take any list.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the schema, the permission and the number parsing that every story needs.

- [x] T003 Write `api/tests/integration/test_migration_0014.py` on the pattern of
  `test_migration_0013.py`. Check:
  - the columns `Request.deleted_at`, `Request.deleted_by` and `Request.deletion_reason` exist
    ([data-model.md](./data-model.md) › requests › New columns);
  - the constraints refuse:
    - a partial mark (`requests_deletion_mark`);
    - an unknown `Request.deletion_reason` (`requests_deletion_reason`);
    - a mark on an approved or linked row (`requests_deletable_status`);
    - a live row with a `NULL` `Request.phone` or `Request.full_name`, and a marked row that still
      has `Request.phone`, `Request.national_id` or `Request.rejection_note` (`requests_erasure`);
  - a marked rejected row with reason `other` and a `NULL` note is accepted (the wrapped
    `requests_rejection_note`);
  - `users_permissions_known` accepts `"delete"`;
  - `requests_pending_idx` has the `deleted_at IS NULL` condition;
  - downgrade and upgrade round-trip.

  Run: **red**.
- [x] T004 Write `api/migrations/versions/0014_subscriber_deletion.py`. Include every column, check
  and index change of [data-model.md](./data-model.md) › requests and › users:
  - the three mark columns;
  - the personal columns made nullable (Names, Identity, Card, Location, Contact);
  - `requests_deletion_mark`, `requests_deletion_reason`, `requests_deletable_status`,
    `requests_erasure`;
  - the three wrapped checks;
  - the pending index;
  - `users_permissions_known`.

  Downgrade restores the 0013 state. It refuses to run when marked rows exist, because erased data
  cannot be made `NOT NULL` again. Run T003: **green**.
- [x] T005 Update `api/app/models/request.py` to match T004:
  - the mark columns, with `Request.deleted_by` → `users.id`;
  - `Mapped[... | None]` for every column in [data-model.md](./data-model.md) › requests › Columns
    made nullable: `Request.first_name`, `Request.father_name`, `Request.grandfather_name`,
    `Request.great_grandfather_name`, `Request.full_name`, `Request.mother_first_name`,
    `Request.mother_second_name`, `Request.no_surname`, `Request.national_id`,
    `Request.national_id_input`, `Request.submitted_national_id`, `Request.family_number`,
    `Request.submitted_family_number`, `Request.family_key`, `Request.birth_date`,
    `Request.issue_date`, `Request.expiry_date`, `Request.birth_place`, `Request.issuing_authority`,
    `Request.card_fields`, `Request.card_readings`, `Request.location_lat`, `Request.location_lng`,
    `Request.location_source`, `Request.address`, `Request.landmark`, `Request.phone`,
    `Request.username`;
  - the same `__table_args__` checks and index;
  - a property `is_deleted`.

  Update `api/app/models/user.py` `users_permissions_known`. Run the whole api suite: **green**.
  Nothing behaves differently yet.
- [x] T006 [P] Extend `api/tests/unit/test_access.py`: `"delete"` is in `ADMIN_PERMISSIONS` after
  `commissions`, `normalize_permissions(["delete"])` passes, and the main admin holds it through
  `has_any_permission`. Run: **red**.
- [x] T007 Add `"delete"` to `ADMIN_PERMISSIONS` in `api/app/core/access.py`
  ([research.md](./research.md) R7). Run T006: **green**.
- [x] T008 [P] Add the label «حذف مشترك (طلب بالانتظار أو مرفوض)» and the key `delete` to the
  permission list in `web/src/lib/labels.ts` and `web/src/auth/access.ts`. Extend
  `web/src/__tests__/access.test.tsx` first. Run: **red**, then **green**.
- [x] T009 [P] Write `api/tests/fixtures/request_number_cases.json` with cases for
  [research.md](./research.md) R6:
  - `"T3C-1005"`, `"t3c-1005"`, `"#T3C-1005"`, `"1005"`, `" 1005 "`, `"١٠٠٥"`, `"۱۰۰۵"` → 1005;
  - `""`, `"T3C-"`, `"10a5"`, `"-1005"`, `"T3C-1005-1"`, `"١٠٠٥x"` → null.

  Copy it to `web/src/__tests__/fixtures/request_number_cases.json`, keeping both copies identical as
  with `page_access.json`.
- [x] T010 [P] Write `api/tests/unit/test_request_number.py` against the fixture. Run: **red**.
- [x] T011 Write `api/app/core/request_number.py::parse(text) -> int | None` (R6). Run T010: **green**.
- [x] T012 [P] Write `web/src/__tests__/requestNumber.test.ts` against the web fixture copy (**red**).
  Then write `web/src/lib/requestNumber.ts::parseRequestNumber` (**green**).
- [x] T013 [P] Write `api/tests/unit/test_deletion_reasons.py` (**red**). It checks:
  - the codes are exactly `duplicate`, `test`, `entry_error`, `other`, in that order, matching
    [data-model.md](./data-model.md) › Deletion reasons;
  - each has its Arabic label;
  - `is_valid` refuses an unknown code.

  Then write `api/app/core/deletion_reasons.py` (**green**). Mirror the codes and labels in
  `web/src/lib/labels.ts`.
- [x] T014 Add helpers next to `request_factory` in `api/tests/helpers/requests.py`.
  `request_factory(status="rejected")` already fills the decision. The helpers:
  - `add_images(db, request, uploads)`: two synthetic files and their `request_images` rows;
  - `add_pin(db, request, admin)`;
  - `add_otp_rows(db, phone, count, draft_id=None)`.

  Run the whole api suite: **green**.

**Checkpoint**: batch 1 ends. The suites are green. Commit.

---

## Phase 3: User Story 1 - Delete a duplicate or test request from its file (Priority: P1) 🎯 MVP

**Goal**: an admin with `review` and `delete` erases a pending or rejected request from its file
after choosing a reason and typing the number.

**Independent Test**: spec US1. Delete a pending test request. The fields are `NULL`, the files, pin
rows and image rows are gone, the row stays, and there is one audit line.

### Tests for User Story 1 (write first, run red)

- [x] T015 [P] [US1] Write `api/tests/integration/test_deletion.py`. A pending request with images,
  pins, two orphan OTP rows for its phone and one live-draft OTP row for the same phone. After
  `POST /admin/requests/{id}/delete` with reason `duplicate` and `confirm_number` `"١٠٠٥"`-style
  input:
  - every erased column of [data-model.md](./data-model.md) › requests is `NULL`;
  - every kept column is unchanged;
  - `Request.deleted_at`, `Request.deleted_by` and `Request.deletion_reason` are set;
  - `status` is still `pending_review`;
  - the `request_images` and `request_number_pins` rows are gone;
  - the files are gone from the uploads directory;
  - the orphan OTP rows are gone, and the live-draft row is kept (R5);
  - the response is the deleted file form of [contracts/api.md](./contracts/api.md).

  The same flow on a rejected request with reason `other` and a note: the note is `NULL`, and
  `rejection_reason`, `rejected_at` and `rejected_by` are kept.

  Run: **red**.
- [x] T016 [P] [US1] In `api/tests/integration/test_deletion.py`, add the refusals in the order of
  [contracts/api.md](./contracts/api.md):
  - 404 for a missing request and for a caller without `review` (including `delete` only);
  - 403 for `review` without `delete`;
  - 409 `request_deleted` on a second delete;
  - 409 `request_not_deletable` for approved and for linked;
  - 422 for an unknown reason;
  - 422 `number_mismatch` for another number and for unparsable text.

  After every refusal the row is unchanged. Run: **red**.
- [x] T017 [P] [US1] In `api/tests/integration/test_deletion.py`, check:
  - a missing image file still lets the deletion finish, and the log names the image id only;
  - a failure injected after the data erasure but before the unlink leaves no image rows, so
    `prune-uploads` removes the left files.

  Run: **red**.
- [x] T018 [P] [US1] Write `api/tests/integration/test_deletion_concurrency.py` on the pattern of
  `test_admin_decide_concurrency.py`:
  - delete and accept race on one request: exactly one wins, and the other gets 409
    (`request_deleted` or `request_not_deletable`);
  - delete and delete race: one 200 and one 409 `request_deleted`.

  Run: **red**.
- [x] T019 [P] [US1] Extend `api/tests/integration/test_admin_decide.py` and `test_admin_pin.py`:
  accept, reject and pin on a deleted pending request return 409 `request_deleted`. Run: **red**.
- [x] T020 [P] [US1] Extend `api/tests/integration/test_audit_completeness.py` and
  `test_log_safety.py`:
  - a deletion writes exactly one `request.deleted` entry, with `before={status, image_count,
    pin_count}` and `after={deleted, reason}` (R12);
  - the entry, the application log and the error responses contain none of the request's name,
    phone, username, national ID, family number, address, landmark or coordinates.

  Run: **red**.
- [x] T021 [P] [US1] Extend `api/tests/integration/test_admin_request_file.py` and
  `test_admin_request_images.py`:
  - the file of a deleted request has `deleted` set, every personal field `null`, and empty
    `images`, `pins`, `linked` and `warnings`;
  - `can_delete` is true only for a caller with `delete` on a live pending or rejected request;
  - an old image id gives 404.

  Run: **red**.
- [x] T022 [P] [US1] Write `web/src/__tests__/deleteRequestDialog.test.tsx`. Check:
  - the warning text;
  - the four reasons;
  - the final button stays disabled until a reason is chosen and `parseRequestNumber` equals the
    number;
  - the API is called with `{reason, confirm_number}`;
  - the server errors are shown in Arabic.

  Run: **red**.
- [x] T023 [P] [US1] Write `web/src/__tests__/deletedRequest.test.tsx`. Check:
  - `RequestReview` shows «حذف» only when `can_delete`;
  - a deleted file shows the banner «تم حذف بيانات هذا الطلب» with who, when and the reason;
  - the decision, pin and delete panels are hidden.

  Run: **red**.

### Implementation for User Story 1

- [x] T024 [US1] Add `DeleteIn` (`reason`, `confirm_number`), the `deleted` block, `can_delete`, and
  nullable personal fields in `RequestFileOut` and its parts to `api/app/schemas/admin_requests.py`
  ([contracts/api.md](./contracts/api.md)).
- [x] T025 [US1] Write `api/app/services/deletion_service.py::delete(db, user, request_id, body)`.
  It follows R3 (lock and check order), R1 (the erasure of every column in
  [data-model.md](./data-model.md) › requests, including `Request.rejection_note`), R4 (the rows in
  the transaction, the unlink after commit, missing files logged by id), R5 (OTP rows with
  `request_id IS NULL`), and R12 (the audit entry and the log line). Run T015–T018 and T020:
  **green**.
- [x] T026 [US1] Update `api/app/services/review_service.py`:
  - `_lock_pending` refuses `is_deleted` with 409 `request_deleted` before the status check (R3);
  - `to_file` returns the deleted form and `can_delete` (R9);
  - `live_check` is skipped for a deleted request;
  - `list_pending` filters `deleted_at IS NULL`.

  Run T019 and T021: **green**.
- [x] T027 [US1] Add `POST /admin/requests/{request_id}/delete` to `api/app/api/admin_requests.py`. It
  calls `deletion_service.delete` and returns `to_file`.
- [x] T028 [P] [US1] Add `deleteRequest(id, body)` and the deleted fields to `web/src/lib/adminRequests.ts`.
- [x] T029 [US1] Write `web/src/pages/admin/pending/DeleteRequestDialog.tsx` (T022: **green**). Wire
  the «حذف» button, the banner and the hidden panels into
  `web/src/pages/admin/pending/RequestReview.tsx` (T023: **green**). Arabic, RTL, phone layout.
- [x] T030 [US1] Add `request.deleted` «حذف مشترك» with the Arabic reason to
  `web/src/lib/auditFormat.ts`. Extend `web/src/__tests__/audit-format.test.ts` first and run it
  **red**, then **green**.

**Checkpoint**: batch 2 ends. US1 works on its own. The suites are green. Commit.

---

## Phase 4: User Story 2 - The phone and the numbers become free again (Priority: P1)

**Goal**: a deleted request blocks nothing. The next request reuses the phone and the numbers and
gets a new number.

**Independent Test**: spec US2.

- [ ] T031 [P] [US2] Write `api/tests/integration/test_deletion_frees_keys.py` (**red**). After a
  deleted pending request:
  - a new draft with the same phone passes the draft phone check;
  - `match_service.find_matches` with the old phone, national ID and family key returns nothing for
    it;
  - a full submit with the same identity is auto-approved as `new`;
  - an OTP request for the phone succeeds at once, even though the deleted request had used 5 codes
    in the hour;
  - the new request's number is greater than every existing number, deleted ones included.
- [ ] T032 [US2] Add `Request.deleted_at.is_(None)` to `_sijil_source` in
  `api/app/services/match_service.py`, as a second guard next to the `NULL` keys (R1). Run T031:
  **green**. Run `test_match_sources.py`: **green**.
- [ ] T033 [P] [US2] Extend `api/tests/integration/test_match_sources.py`. `requests_erasure` makes a
  marked row with its keys still set impossible, so test the second guard through the query instead:
  the compiled `_sijil_source` query filters `deleted_at IS NULL`. Run: **red**, then **green** with
  T032.

**Checkpoint**: the keys are freed.

---

## Phase 5: User Story 3 - The main admin grants «حذف» (Priority: P2)

**Goal**: the `delete` switch on the admins page.

**Independent Test**: spec US3.

- [ ] T034 [P] [US3] Extend `api/tests/integration/test_admins_manage.py` (**red**):
  - the main admin creates and updates an admin with `delete`;
  - the change writes `user.permissions_changed` with before and after;
  - a marketer cannot hold it;
  - the main admin's own permissions show `delete` as always on.
- [ ] T035 [US3] Make T034 **green**. The code should only need T007. Fix
  `api/app/services/account_service.py` only if a test shows a gap.
- [ ] T036 [P] [US3] Write the switch test in `web/src/__tests__/admins-permissions.test.tsx`
  (**red**):
  - the «حذف مشترك» switch appears for an added admin, off by default;
  - it is on and locked for the main admin.
- [ ] T037 [US3] Add the switch to `web/src/pages/admin/Admins.tsx` from the labels list (T008). Run
  T036: **green**.
- [ ] T038 [P] [US3] Extend `web/src/__tests__/deletedRequest.test.tsx`: an admin with `review` but
  without `delete` sees no «حذف» button. Run: **red**, then **green** (the button follows
  `can_delete`).
- [ ] T039 [US3] In `api/tests/integration/test_deletion.py`, add the case: `delete` turned off for an
  admin, then the delete attempt gets 403. Run: **red**, then **green**.
- [ ] T040 [US3] Run the whole api and web suites: **green**.

**Checkpoint**: batch 3 ends. Commit.

---

## Phase 6: User Story 4 - Other requests and screens show «سجل محذوف» (Priority: P2)

**Goal**: linked records, audit lines and counts behave right around a deleted request.

**Independent Test**: spec US4.

- [ ] T041 [P] [US4] Extend `api/tests/integration/test_linked_records.py` (**red**): pending B with
  reason `family_exists` pointing to deleted A gets
  `{available: false, deleted: true, number_label}` and nothing else. B's reasons are unchanged.
  Accepting and rejecting B still work.
- [ ] T042 [US4] Update the `_sijil` resolver in `api/app/services/linked_records.py` and add the
  `deleted` and `number_label` fields of `LinkedRecord` in `api/app/schemas/admin_requests.py` (R10).
  Run T041: **green**.
- [ ] T043 [P] [US4] Extend `web/src/__tests__/requestReview.test.tsx` or add
  `linkedRecordCard.test.tsx` (**red**): a deleted linked record shows «سجل محذوف (#T3C-…)» with no
  images or fields.
- [ ] T044 [US4] Update `web/src/pages/admin/pending/LinkedRecordCard.tsx`. Run T043: **green**.
- [ ] T045 [P] [US4] Extend `api/tests/integration/test_audit_viewer.py` (**red**):
  - entries of a deleted request carry `entity_deleted: true`, and other entries carry `false`;
  - the old `request.numbers_pinned` and `request.rejected` entries are byte-for-byte unchanged after
    the deletion.
- [ ] T046 [US4] Add `entity_deleted` in `api/app/services/audit_service.py` and `api/app/api/audit.py`
  (R12). Run T045: **green**.
- [ ] T047 [US4] In `web/src/lib/auditFormat.ts`, show «سجل محذوف» in place of the pin link when
  `entity_deleted` is set. Extend `web/src/__tests__/audit-format.test.ts` first and run it **red**,
  then **green**.
- [ ] T048 [P] [US4] Extend `api/tests/integration/test_admin_home.py` (**red**): deleting a pending
  request lowers `pending` by one. Deleting a pending and a rejected request leaves `submitted` and
  `rejected` for today and the month unchanged.
- [ ] T049 [US4] Add `deleted_at IS NULL` to the pending count in `api/app/services/admin_home.py`
  (R13). Run T048: **green**.

---

## Phase 7: User Story 6 - Open any request by its number (Priority: P2)

**Goal**: «فتح طلب برقمه» reaches any submitted request, rejected ones included.

**Independent Test**: spec US6.

- [ ] T050 [P] [US6] Write `api/tests/integration/test_by_number.py` (**red**):
  - `GET /admin/requests/by-number/{text}` returns `{id}` for pending, approved, rejected, linked and
    deleted requests, with each fixture format;
  - an unknown number gives 404 with «لا يوجد طلب بهذا الرقم»;
  - a caller without `review` gets the same 404;
  - unparsable text gives the same 404.
- [ ] T051 [US6] Add `find_by_number` to `api/app/services/review_service.py` and the route to
  `api/app/api/admin_requests.py`. Declare it before `/requests/{request_id}` so the paths do not
  clash. Run T050: **green**.
- [ ] T052 [P] [US6] Write `web/src/__tests__/openByNumber.test.tsx` (**red**):
  - the box navigates to `/admin/pending/:id` on success;
  - it shows «لا يوجد طلب بهذا الرقم» on 404;
  - the button is disabled while the text does not parse.
- [ ] T053 [US6] Write `web/src/pages/admin/pending/OpenByNumber.tsx` and place it at the top of
  `PendingList.tsx`. Add `findByNumber` to `web/src/lib/adminRequests.ts`. Run T052: **green**. Run
  the suites: **green**.

**Checkpoint**: batch 4 ends. Commit.

---

## Phase 8: User Story 5 - The marketer sees that a request was deleted (Priority: P3)

**Goal**: the marketer sees «محذوف» with the reason, number, tower and date only.

**Independent Test**: spec US5.

- [ ] T054 [P] [US5] Extend `api/tests/integration/test_requests_api.py` and `test_marketer_privacy.py`
  (**red**):
  - the list and the detail of a deleted request return `result: "deleted"`, `deleted_at`,
    `deletion_label`, the number, the tower and `submitted_at`;
  - every other field is `null` ([contracts/api.md](./contracts/api.md) › marketer);
  - no admin name appears;
  - a deleted rejected request has the reason's name only and no note.
- [ ] T055 [US5] Make the erased fields nullable and add `deleted` to `ResultCode`, plus `deleted_at`
  and `deletion_label`, in `api/app/schemas/requests.py`. Update the marketer `to_out` in
  `api/app/services/submit_service.py` (R11). Run T054: **green**.
- [ ] T056 [P] [US5] Write `web/src/__tests__/marketerDeleted.test.tsx` (**red**):
  - `SubmittedTab` shows the grey tag «محذوف» and the reason;
  - `RequestResult` shows only the kept fields and no copy or share buttons.
- [ ] T057 [US5] Update `web/src/lib/requests.ts`, `web/src/lib/requestStatus.ts`,
  `web/src/pages/marketer/SubmittedTab.tsx` and `web/src/pages/marketer/RequestResult.tsx`. Run T056:
  **green**. Run `dashboard.test.tsx` and `requestResult.test.tsx`: **green**.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T058 [P] Write `e2e/tests/subscriber-deletion.spec.ts` with synthetic data. It covers:
  - the marketer submits two family requests;
  - the delete admin deletes A with typed Arabic-Indic digits;
  - B shows «سجل محذوف»;
  - the marketer sees «محذوف» and reuses the phone;
  - the delete admin opens a rejected request by number and deletes it.

  Write it and run it **red** against the batch-4 build (no marketer «محذوف» view yet), then run it
  **green** after T057.
- [ ] T058a [P] Update the stale feature numbers in code comments after the renumbering (for example
  `api/app/api/marketer.py` "until feature 011" → 013, `api/app/services/admin_home.py` "012 adds
  `linked_at`" → 013).
- [ ] T059 [P] Run `npm run lint`, `npm run typecheck`, `ruff check` and `ruff format --check`
  across `api/` and `web/`, and fix what they find.
- [ ] T060 [P] Check the changed Markdown files with Prettier. Strip any `\r` written by host scripts
  first.
- [ ] T061 Run the full api suite, the web suite and e2e: **green**.
- [ ] T062 Run `docker compose up`. Walk through the [quickstart.md](./quickstart.md) manual scenarios
  1–14 on the running app, with synthetic data.
- [ ] T063 Write `specs/011-subscriber-deletion/manual-test-ar.md`, the owner's Arabic manual test
  steps (CLAUDE.md).
- [ ] T064 [P] Confirm `docs/system.md` v1.15 §7.4 and the constitution v1.3.0 match what was built.
  Note any difference to the owner instead of changing the rules silently.
- [ ] T065 Mark all tasks done in this file.
- [ ] T066 Commit batch 5.

**Checkpoint**: batch 5 ends. The feature is ready for review.

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T014)**: blocks every story. T004 needs T003 (red
  first). T005 needs T004. T011 needs T010.
- **US1 (T015–T030)** needs Foundational. It is the MVP.
- **US2 (T031–T033)** needs US1 (it deletes through the service).
- **US3 (T034–T040)** needs T007. It can run beside US1, except T038 and T039, which need T029 and
  T025.
- **US4 (T041–T049)** needs US1.
- **US6 (T050–T053)** needs Foundational (T011). It can run beside US1. The delete flow from it needs
  US1.
- **US5 (T054–T057)** needs US1.
- **Polish (T058–T066)** needs every story.

Within each story: the tests come first and are run red, then the schemas, the services, the routes
and the web.

## Parallel Example: Foundational

```text
T006 test_access.py   |  T009 fixture  |  T013 deletion reasons
then: T007 | T010 → T011 | T012 (web parse)
```

## Parallel Example: User Story 1

```text
T015, T016, T017, T018, T019, T020, T021 (api tests) | T022, T023 (web tests)
then: T024 → T025 → T026 → T027 ; T028 → T029 ; T030
```

## Implementation Strategy

- **Batches 1–2** (Foundational + US1) deliver the MVP: a duplicate or test request can be erased
  safely and audited.
- **Batch 3** frees the phone and the numbers, the practical goal of the deletion, and adds the
  permission switch.
- **Batch 4** fixes the views around a deleted request and adds the way to reach rejected requests.
- **Batch 5** adds the marketer view, e2e and the owner's manual test.

## Notes

- Never place real card images or real subscriber data in tests, fixtures or e2e (CLAUDE.md).
- Python host scripts write CRLF. Write with `newline="\n"` before Prettier runs.
- Each commit message ends with the Co-Authored-By line.
