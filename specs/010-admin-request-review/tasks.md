---

description: "Task list for feature 010: Admin Review of Pending Requests"
---

# Tasks: Admin Review of Pending Requests

**Input**: Design documents from `specs/010-admin-request-review/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's rule: **each new test is run
red before its code is written**. Report red and green for every test task.

**Test rules**:
- Use only synthetic data: the fake card reader and made-up numbers (for example national ID
  `199000000001`, family number `1234A5678901234567`). No real card images and no real subscribers.
- OTP uses `FakeOtpSender` / `OTP_FAKE_CODE`.
- Pending requests are inserted with `api/tests/helpers/requests.py::request_factory`, or submitted
  end to end with `api/tests/helpers/submit.py` when the reasons must come from the real decision.
- Users come from the `make_user` fixture: the main admin, an admin with `review`, an admin with only
  `settings`, and a marketer.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each ends at a phase boundary and with a commit):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T011 |
| 2 | 3 (US1 list, file, images) | T012–T024 |
| 3 | 4 (US2 accept and reject) | T025–T038 |
| 4 | 5 (US3 pin numbers, warnings) | T039–T049 |
| 5 | 6–8 (US4 reminder, US5 home, Polish) | T050–T062 |

---

## Phase 1: Setup

- [x] T001 Add the error codes of [contracts/api.md](./contracts/api.md) › New error messages to
  `api/app/errors.py`, with their Arabic messages and statuses:
  - 409: `already_decided`, `warnings_unconfirmed`;
  - 422: `commission_answer_required`, `rejection_note_required`, `pin_source_empty`,
    `invalid_national_id`, `invalid_family_number`.
- [x] T002 [P] Write `api/tests/integration/test_migration_0013.py` on the pattern of
  `test_migration_0012.py`. Check:
  - the new columns exist;
  - `submitted_national_id` and `submitted_family_number` are backfilled from existing rows;
  - the constraints refuse: a rejected request without `rejected_at`, `other` without a note, a note
    with a non-`other` reason, an unknown `rejection_reason`, an unknown reason `state`, and a pin
    with `source='mrz'` on `family_number`;
  - `image_access_log.draft_id` accepts null;
  - downgrade and upgrade round-trip.

  Run: **red**.
- [x] T003 Write migration `api/migrations/versions/0013_admin_review.py` (down revision `0012`)
  exactly as in [data-model.md](./data-model.md). It covers:
  - `requests.submitted_national_id` and `requests.submitted_family_number` (backfill, then not
    null), `requests.counts_commission`, `requests.approval_warnings`, `requests.rejected_at`,
    `requests.rejected_by`, `requests.rejection_reason`, `requests.rejection_note`, the three new
    checks and `requests_pending_idx`;
  - `request_reasons.state`, `request_reasons.state_changed_at`,
    `request_reasons.state_changed_by` and `request_reasons.added_by`;
  - the table `request_number_pins` (data-model.md › request_number_pins.request_id,
    request_number_pins.field, request_number_pins.previous_value, request_number_pins.value,
    request_number_pins.source with its checks, request_number_pins.pinned_by,
    request_number_pins.pinned_at, plus the index);
  - `image_access_log.draft_id` nullable and `image_access_log.request_id`.

  The downgrade reverses all of it. Under `pending_review → rejected` the 008 check
  `requests_pending_no_time` still holds, and the new check `status = 'rejected'` ⇒
  `approved_at IS NULL` is added. T002 **green**.
- [x] T004 Mirror the migration in the models:
  - `api/app/models/request.py`: the new `Request` columns and checks, the `RequestReason` state
    columns, `REASON_STATES`, and the new `RequestNumberPin` model with a `Request.pins`
    relationship;
  - `api/app/models/draft.py`: `ImageAccessLog.request_id`, and `draft_id` becomes `Mapped[uuid.UUID | None]`;
  - export `RequestNumberPin` from `api/app/models/__init__.py`.

  Run the full api suite: green, with no change in 008/009 behavior.
- [x] T005 Set `submitted_national_id=draft.national_id` and
  `submitted_family_number=draft.family_number` when a request is created in
  `api/app/services/submit_service.py`, and in the test factory
  `api/tests/helpers/requests.py::request_factory` (defaults equal to `national_id` and
  `family_number`). This covers data-model.md › requests.submitted_national_id and
  requests.submitted_family_number. Extend `api/tests/integration/test_submit.py` with one assertion
  that both are stored. Run it red first, then green.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the pure rules (R5, R6), the linked-record registry (R8), the Baghdad day bounds (R10) and
the permission dependency used by every review route.

- [x] T006 [P] Write `api/tests/unit/test_review_check.py` for `review(type, return_refs, return_basis,
  matches, prior_conflict_refs)` ([research R5](./research.md#r5-re-check-and-warnings)). Cover:
  - `new` with a family-only record → open `family_exists` row, `new_type='additional'`, no warning;
  - `additional` with the family record gone → no open family row, type stays `additional`;
  - `new` with a same-person record → warning `same_person`;
  - `additional` with a same-person record → warning `same_person`;
  - a national-ID-only record not in `prior_conflict_refs` → open `numbers_conflict` row and warning
    `id_conflict`;
  - one that is in `prior_conflict_refs` → the open row, no warning;
  - `return` with basis `identity` whose target is no longer `same_person` → `return_target_lost`;
  - `return` with basis `phone` → never `return_target_lost`;
  - `return` with a family-only record outside the target → open `family_exists`, type stays
    `return`;
  - no matches → nothing.

  Run: **red**.
- [x] T007 Implement `api/app/core/review_check.py` (pure, no database). It defines the `ReviewCheck`
  dataclass of data-model.md › ReviewCheck (`open_rows`, `new_type`, `warnings`), with warning kinds
  limited to `same_person`, `id_conflict`, `return_target_lost`, and the function `review(...)`.
  It reuses the views in `app/core/matches.py`. T006 **green**.
- [x] T008 [P] Write `api/tests/unit/test_rejection_reasons.py`. Cover:
  - each code has its Arabic label;
  - `other` needs a note of 3 to 300 characters after trimming; spaces only count as empty;
  - a note with any other code is refused;
  - the display label is the Arabic label, or the trimmed note for `other`.

  Then implement `api/app/core/rejection_reasons.py`: the codes and labels of
  [research R6](./research.md#r6-rejection-reasons-fr-019) (data-model.md ›
  requests.rejection_reason and requests.rejection_note), `validate(reason, note) -> str | None`
  raising `AppError`, and `label(reason, note)`. Run red, then green.
- [x] T009 [P] Add `baghdad_today_bounds(at=None) -> tuple[datetime, datetime]` to
  `api/app/core/timeutil.py`, with tests in `api/tests/unit/test_timeutil.py`: 23:30 Baghdad belongs to
  that Baghdad day, and 00:30 Baghdad to the next one, which is still the previous UTC day. Run red,
  then green.
- [x] T010 Create `api/app/services/linked_records.py`
  ([research R8](./research.md#r8-linked-records)):
  - `register_resolver(source, fn)` and `resolve(db, refs) -> dict[(source, ref), LinkedRecordOut]`;
  - a missing resolver or a missing row gives `available=False`;
  - register the `sijil` resolver. It reads `Request` rows and returns the fields of data-model.md ›
    LinkedRecord, with `registered_at=submitted_at`, `image_ids` from `request_images` and
    `expiry=None`.

  Test it in `api/tests/integration/test_linked_records.py`: a sijil record resolves, an unknown
  source and a missing id give unavailable, and the result never includes `card_readings`. Run red,
  then green.
- [x] T011 Create `api/app/schemas/admin_requests.py` with the response and body models of
  [contracts/api.md](./contracts/api.md). Use `extra="forbid"` on the bodies:
  - `PendingList` and `PendingItem`;
  - `RequestFileOut`, `NumbersOut`, `ReasonOut`, `LinkedRecordOut` and `DecisionOut`;
  - `AcceptIn`, `RejectIn` and `PinIn` (fields `field`, `source`, `value?`);
  - `HomeCounts` and `HomeOut`.

  Create `api/app/api/admin_requests.py`, an empty router under `/admin`, with
  `review_only = require_permission("review")`, and include it in `api/app/main.py`.

**Checkpoint (batch 1)**: the full api suite is green. Commit.

---

## Phase 3: User Story 1 - See the pending list and open a request (Priority: P1) 🎯 MVP

**Goal**: an admin with `review` lists pending requests, filters them by reason, and opens the full
file with its linked records and images, with each image opening logged.

**Independent Test**: spec.md › User Story 1 › Independent Test.

### Tests for User Story 1

- [x] T012 [P] [US1] Write `api/tests/integration/test_admin_pending_list.py`. Submit five requests
  end to end (family, edited numbers, conflict, return by identity, return by phone) plus one
  approved and one rejected. Check:
  - `GET /api/admin/requests/pending` returns exactly the five, oldest first, with `total=5`, type,
    reason codes, marketer name, full name, tower and `submitted_at`;
  - `?reason=numbers_conflict` returns one;
  - a request with two reasons appears under both filters;
  - an unknown reason gives 422;
  - the `settings` admin and the marketer get 403;
  - the main admin gets 200.

  Run: **red**.
- [x] T013 [P] [US1] Write `api/tests/integration/test_admin_request_file.py`. Check:
  - the file has every field of contracts/api.md › GET /admin/requests/{id};
  - `numbers.*.reading` comes from `card_fields[field].original`, `numbers.national_id.mrz` from
    `national_id_check.mrz`, and `numbers.*.marketer` from `submitted_*`;
  - each reason has its state, and `record` is filled by the resolver with the right basis
    (`identity`/`phone` on return rows);
  - `warnings` is `[]` for a fresh request;
  - the JSON never contains `card_readings` or `raw`;
  - a decided request returns with `decision` set;
  - a request whose marketer is archived is still returned, with the marketer's name (spec Edge
    Cases);
  - a missing id, the `settings` admin and the marketer all get 404.

  Run: **red**.
- [x] T014 [P] [US1] Write `api/tests/integration/test_admin_request_images.py`. Check:
  - the `review` admin gets the JPEG of a request image and of a linked sijil record's image;
  - each open adds an `image_access_log` row with `request_id`, `draft_id = requests.draft_id`,
    the side and `purpose='view'`;
  - the `settings` admin and the marketer get 404 and no log row;
  - a missing file gives 404 `image_not_found`, and the log line has no path.

  Run: **red**.

### Implementation for User Story 1

- [x] T015 [US1] Create `api/app/services/review_service.py` with `list_pending(db, reason)`
  ([research R13](./research.md#r13-pending-list-fr-002)):
  - oldest `submitted_at` first, with `total`;
  - the reason filter uses `EXISTS` on `request_reasons` with
    `state <> 'not_applicable'` (data-model.md › request_reasons.state);
  - each item's codes come from rows that are not `not_applicable`.
- [x] T016 [US1] Add `get_file(db, request_id) -> RequestFileOut` to
  `api/app/services/review_service.py`:
  - `numbers` from `card_fields`, `national_id_check`, `submitted_*`, the current values and `pins`;
    `edited` is true when the field is listed in a `numbers_edited` row;
  - `names_reading` from `card_fields[*].original`;
  - `reasons` resolved through `linked_records.resolve`;
  - `warnings` from a `_live_check(db, request)` helper, which runs `match_service.find_matches` on
    the phone and current numbers, drops the request's own `(sijil, id)`, and calls
    `review_check.review`;
  - `decision` for decided requests.
- [x] T017 [US1] Add `open_request_image(db, user, image_id)` to
  `api/app/services/review_service.py`
  ([research R9](./research.md#r9-image-access-for-review-fr-005)). It finds `RequestImage`, checks
  `has_any_permission(..., ["review"])` (404 otherwise), checks that the file exists, and writes
  `ImageAccessLog(request_id=…, draft_id=request.draft_id, side=…, purpose='view')`
  (data-model.md › image_access_log.request_id).
- [x] T018 [US1] Add these routes to `api/app/api/admin_requests.py`:
  - `GET /admin/requests/pending` (403 for non-review);
  - `GET /admin/requests/{id}` (404 for non-review, checked inside the route so existence does not
    leak);
  - `GET /admin/request-images/{image_id}` (`FileResponse`, `image/jpeg`, no-store cache header as
    for draft images).

  T012, T013 and T014 **green**.
- [x] T019 [P] [US1] Create `web/src/lib/adminRequests.ts`: the types of contracts/api.md and the calls
  `listPending(reason?)`, `getRequestFile(id)` and `requestImageUrl(id)` (an authenticated blob fetch,
  as `drafts.ts` does for draft images). Add to `web/src/lib/labels.ts`:
  - the reason labels (اشتراك إضافي، إعادة للخدمة، تعديل الأرقام، تعارض بالأرقام);
  - the state labels (لم يعد ينطبق، تم التثبيت);
  - the basis labels (إعادة للخدمة بالرقم الوطني والعائلي، إعادة للخدمة بالهاتف، تعارض بالأرقام، عائلة موجودة);
  - the source labels (سِجلّ، قديم، SAS);
  - the type labels (جديد، اشتراك إضافي، إعادة للخدمة).
- [x] T020 [P] [US1] Write `web/src/__tests__/adminPendingList.test.tsx`. Check:
  - the rows render with labels and Baghdad time;
  - the reason filter chips call `listPending` with the code;
  - the count shows;
  - an empty list shows «لا توجد طلبات بالانتظار».

  Run: **red**.
- [x] T021 [US1] Create `web/src/pages/admin/pending/PendingList.tsx`:
  - filter chips by reason, the count, and rows (cards on a phone) that link to
    `/admin/pending/:id`;
  - replace `AdminPending` in `web/src/pages/admin/placeholders.tsx` and `web/src/router.tsx`;
  - add the child route `pending/:id` under the same `page('pending', …)` guard.

  T020 **green**.
- [x] T022 [P] [US1] Create `web/src/pages/admin/pending/LinkedRecordCard.tsx`. It shows the source,
  basis, name, username, phone, tower, registration date, the status chip with the §7.2 colors from
  `requestStatus.ts`, the image thumbnails, «سجل غير متوفر» when `available=false`, and the state
  label when the reason is not open.
- [x] T023 [P] [US1] Write `web/src/__tests__/requestReview.test.tsx`: every section renders from a
  fixture file, the linked-record card shows its basis label, and an unavailable record shows
  «سجل غير متوفر». Run: **red**.
- [x] T024 [US1] Create `web/src/pages/admin/pending/RequestReview.tsx` (`/admin/pending/:id`). It has
  these sections:
  - البطاقة: names, the two numbers, dates, place, and both images with «الصورة غير متوفرة» on
    error;
  - الموقع: the map, or the coordinates link when no map key is set, with address and landmark;
  - الاشتراك;
  - الهاتف;
  - الأسباب, with the LinkedRecordCards;
  - a placeholder area for the decision.

  The page is RTL and stacks on a phone. T023 **green**.

**Checkpoint (batch 2)**: US1 works on its own (read-only review). The full suites are green. Commit.

---

## Phase 4: User Story 2 - Accept or reject (Priority: P1)

**Goal**: one decision per request, stored on it and audited. The commission answer is asked for a
return, and the rejection reason comes from the fixed list. The marketer sees the outcome.

**Independent Test**: spec.md › User Story 2 › Independent Test.

### Tests for User Story 2

- [x] T025 [P] [US2] Write `api/tests/integration/test_admin_decide.py`. Check accept:
  - a family request accepted → `approved`, `approved_by` = the admin, `approved_at` = the frozen
    clock, `counts_commission=true`, username unchanged;
  - a return without `counts_commission` → 422 `commission_answer_required`; with `false` → it is
    stored as false;
  - `counts_commission` on a non-return → 422.

  Check reject:
  - `card_unclear` → `rejected` with `rejected_by`, `rejected_at` and the reason, and no note;
  - `other` with "  " → 422 `rejection_note_required`; with a note → stored trimmed;
  - a note with `card_unclear` → 422.

  Check the rest:
  - accept or reject of an already decided request → 409 `already_decided` with `extra.status`;
  - non-review callers get 404;
  - after the reject, a new draft with the same phone and numbers is checked as if the request did
    not exist (FR-018).

  Run: **red**.
- [x] T026 [P] [US2] Write `api/tests/integration/test_admin_decide_concurrency.py` on the pattern of
  `test_submit_concurrency.py`. Two sessions accept and reject the same request at once: exactly one
  succeeds, the other gets 409 `already_decided`, and the row holds one decision (SC-003). Run:
  **red**.
- [x] T027 [P] [US2] Extend `api/tests/integration/test_requests_api.py` (marketer). After an accept:
  `result='approved'` and the username is present. After a reject with `other`: `result='rejected'`,
  `rejection_reason='other'`, `rejection_label` = the note, and `rejected_at` is set. After a reject
  with `card_unclear`: the label is «صورة البطاقة غير واضحة». Run: **red**.
- [x] T028 [P] [US2] Extend `api/tests/integration/test_marketer_privacy.py`. After accept and after
  reject, the marketer's `GET /requests/{id}` and the list contain no linked record field, no
  warnings, no admin name and no reason details (SC-004). Run: **red** (the new fields do not exist
  yet, so the shape assertion fails).

### Implementation for User Story 2

- [x] T029 [US2] Add `accept(db, user, request_id, body)` to `api/app/services/review_service.py`
  ([research R2](./research.md#r2-one-decision-per-request-fr-009),
  [R7](./research.md#r7-accept-with-the-commission-answer-and-with-warnings)). It:
  1. locks the row with `SELECT … FOR UPDATE`;
  2. checks that it is pending (else 409 `already_decided`);
  3. applies the commission rule (data-model.md › requests.counts_commission);
  4. recomputes the warnings with `_live_check` and compares them with `confirm_warnings` (409
     `warnings_unconfirmed` with `extra.warnings` when they differ);
  5. sets `status`, `approved_at=utc_now()`, `approved_by` and `approval_warnings`
     (data-model.md › requests.approval_warnings, null when empty);
  6. writes the audit `request.approved` of [research R12](./research.md#r12-audit-and-logs-fr-017);
  7. commits.

  Log only the number and the action.
- [x] T030 [US2] Add `reject(db, user, request_id, body)` to `api/app/services/review_service.py`. It
  takes the same lock and pending check, calls `rejection_reasons.validate`, sets `rejected_at`,
  `rejected_by`, `rejection_reason` and `rejection_note` (data-model.md › requests.rejected_at,
  requests.rejected_by, requests.rejection_reason, requests.rejection_note), and writes the audit
  `request.rejected` (R12).
- [x] T031 [US2] Add `POST /admin/requests/{id}/accept` and `POST /admin/requests/{id}/reject` to
  `api/app/api/admin_requests.py`. Both return the request file, and non-review callers get 404.
  T025 and T026 **green**.
- [x] T032 [US2] Add `rejection_reason`, `rejection_label` and `rejected_at` to `RequestOut` in
  `api/app/schemas/requests.py`, and fill them in `submit_service.to_out` through
  `rejection_reasons.label` ([research R11](./research.md#r11-marketer-view-fr-011)). T027 and T028
  **green**.
- [x] T033 [P] [US2] Write `web/src/__tests__/decisionPanel.test.tsx`. Check:
  - «قبول» on a family request calls `accept` with `{}` after the confirm dialog;
  - on a return, the dialog «هل تُحتسب عمولة للمسوّق؟» needs نعم or لا before sending;
  - a 409 `already_decided` shows «تم البت في هذا الطلب مسبقاً» and reloads the file;
  - a decided request shows the decision read-only with no buttons.

  Run: **red**.
- [x] T034 [P] [US2] Write `web/src/__tests__/rejectDialog.test.tsx`. Check:
  - the five reasons are listed;
  - «سبب آخر» shows a required text field with the hint «لا تكتب أي معلومة عن مشترك آخر», and sending
    is disabled until it has 3 or more characters after trimming;
  - another reason sends no note.

  Run: **red**.
- [x] T035 [US2] Add `accept(id, body)` and `reject(id, body)` to `web/src/lib/adminRequests.ts`, and
  the rejection labels to `web/src/lib/labels.ts`, mirroring `api/app/core/rejection_reasons.py`.
- [x] T036 [US2] Create `web/src/pages/admin/pending/RejectDialog.tsx` and
  `web/src/pages/admin/pending/DecisionPanel.tsx` (accept confirm, return commission dialog,
  already-decided handling, read-only decision view), and mount the panel in `RequestReview.tsx`.
  T033 and T034 **green**.
- [x] T037 [US2] Show «تم رفض الطلب» with `rejection_label` in
  `web/src/pages/marketer/RequestResult.tsx` and in the rejected rows of
  `web/src/pages/marketer/SubmittedTab.tsx`, and add the fields to `web/src/lib/requests.ts`. Extend
  `web/src/__tests__/requestResult.test.tsx`: run red, then green.
- [x] T038 [US2] Add the labels for `request.approved` and `request.rejected` to
  `web/src/lib/auditFormat.ts`, including «قبول رغم التحذير» when `despite_warnings` is not empty.
  Extend `api/tests/integration/test_audit_completeness.py` and `test_log_safety.py`: accept and
  reject entries exist, and neither they nor the log lines contain the national ID, family number,
  phone or names. Run red, then green.

**Checkpoint (batch 3)**: pending requests can be decided end to end. The full suites are green.
Commit.

---

## Phase 5: User Story 3 - Check and pin edited numbers (Priority: P2)

**Goal**: pin a number from the reading, the MRZ, the marketer or typed by the admin. The re-check
marks the reasons, may turn `new` into `additional`, and raises red warnings that need a confirmed
accept.

**Independent Test**: spec.md › User Story 3 › Independent Test.

### Tests for User Story 3

- [x] T039 [P] [US3] Write `api/tests/integration/test_admin_pin.py`. Check:
  - **Sources**: the reading's family number, the MRZ national ID, the marketer's value, and a
    typed national ID in Arabic digits (normalized). `value` with a non-typed source → 422. `mrz` on
    `family_number` → 422. A source with no value → 422 `pin_source_empty`.
  - **Validation**: a typed national ID of 11 digits → 422 `invalid_national_id`; a family number
    of only symbols → 422 `invalid_family_number`.
  - **Storage**: one pin row per call (data-model.md › request_number_pins); `national_id`,
    `family_number` and `family_key` are updated; `submitted_*` and `card_fields` are unchanged.
  - **Re-check** (FR-014, FR-015): pinning to an existing family turns `new` into `additional`,
    adds an open `family_exists` row with `added_by`, and marks `numbers_edited` `resolved` once
    every edited field is pinned. Pinning away from a family match marks that row
    `not_applicable`. Pinning back reopens it.
  - **Warnings** (FR-019a): pinning to the numbers of an existing subscriber on a `new` request
    puts `same_person` in the file's `warnings`. Accept without `confirm_warnings` → 409
    `warnings_unconfirmed`. With `["same_person"]` → accepted, `approval_warnings` is stored, and
    the audit has `despite_warnings`.
  - **Other**: pinning a decided request → 409 `already_decided`; non-review → 404.

  Run: **red**.
- [x] T040 [P] [US3] Write `api/tests/integration/test_admin_pin_concurrency.py`. A pin to family F and
  a marketer submission with family F run at once: whichever runs second sees the other (the
  submission becomes a family match, or the pin finds the new request), so neither misses it. Also
  run two pins with swapped values (request X from national ID A to B, request Y from B to A) at
  once: both finish, with no deadlock (research R4). Run: **red**.

### Implementation for User Story 3

- [x] T041 [US3] Add `pin(db, user, request_id, body)` to `api/app/services/review_service.py`
  ([research R4](./research.md#r4-pinning-numbers)). It:
  1. locks the row and checks that it is pending;
  2. resolves the value from the source (data-model.md › request_number_pins.source,
     request_number_pins.value);
  3. validates it with `normalize_national_id` or `family_key`;
  4. takes the advisory locks for the old and new values in the submission order: every
     `match:nid:*` key first, de-duplicated and sorted, then every `match:family:*` key, the same
     way (research R4);
  5. inserts a `RequestNumberPin` with `previous_value` = the field's current value,
     `pinned_by` = the admin and `pinned_at = utc_now()` (data-model.md ›
     request_number_pins.request_id, request_number_pins.previous_value,
     request_number_pins.pinned_by, request_number_pins.pinned_at), then updates the request
     columns.
- [x] T042 [US3] In the same `pin`, run `_live_check`, then apply the result
  ([research R3](./research.md#r3-reason-state)):
  - add the missing open rows with `added_by` (data-model.md › request_reasons.added_by);
  - mark the gone match rows `not_applicable` and reopen the returned ones, with
    `state_changed_at` and `state_changed_by` (data-model.md › request_reasons.state,
    request_reasons.state_changed_at, request_reasons.state_changed_by);
  - mark `numbers_edited` `resolved` when every field in `details.fields` has a pin;
  - set `type` to `new_type`;
  - write the audit `request.numbers_pinned` with `pin_id` (R12; no values, constitution III
    v1.2.1);
  - commit.

  Pass the request's open `numbers_conflict` refs as `prior_conflict_refs`, so only a new conflict
  warns.
- [x] T043 [US3] Add `POST /admin/requests/{id}/pin` to `api/app/api/admin_requests.py`, returning the
  file. T039 and T040 **green**.
- [x] T044 [P] [US3] Write `web/src/__tests__/numbersPinPanel.test.tsx`. Check:
  - for each edited field, the reading, the MRZ (national ID only), the marketer's value and the
    current value are shown side by side, and differences are highlighted;
  - «لم تقرأه البطاقة» shows when there is no reading;
  - «تثبيت القيمة» on a source calls `pin` with that source and no value;
  - the typed input calls `pin` with `typed` and the value;
  - the pins history lists who and when;
  - a 422 shows its Arabic message.

  Run: **red**.
- [x] T045 [US3] Add `pin(id, body)` to `web/src/lib/adminRequests.ts`, then create
  `web/src/pages/admin/pending/NumbersPinPanel.tsx` and mount it in `RequestReview.tsx` when there is
  a `numbers_edited` reason. T044 **green**.
- [x] T046 [P] [US3] Extend `web/src/__tests__/decisionPanel.test.tsx`. Check:
  - with `warnings` not empty, a red alert names each kind (labels in `labels.ts`):
    - «تحذير: الأرقام المثبّتة تطابق مشتركاً موجوداً (نفس الشخص)»;
    - «تحذير: الرقم الوطني يطابق مشتركاً آخر برقم عائلي مختلف»;
    - «تحذير: أرقام طلب العودة لم تعد تطابق المشترك المرتبط»;
  - «قبول» opens the second confirmation «القبول رغم التحذير؟» and sends `confirm_warnings`;
  - a 409 `warnings_unconfirmed` reloads and asks again with the new kinds.

  Run: **red**.
- [x] T047 [US3] Implement the warning alert and the second confirmation in
  `web/src/pages/admin/pending/DecisionPanel.tsx`, and add the warning labels to
  `web/src/lib/labels.ts`. T046 **green**.
- [x] T048 [US3] Add the label for `request.numbers_pinned` to `web/src/lib/auditFormat.ts`. Extend
  `api/tests/integration/test_log_safety.py` and `test_audit_completeness.py`: a pin entry exists,
  it holds `pin_id`, and that pin row's `previous_value` and `value` give the before and after
  (constitution III v1.2.1). Neither the entry nor the log line contains the pinned value, the old
  value, the phone or names. Run red, then green.
- [x] T049 [US3] Extend `api/tests/integration/test_marketer_privacy.py`: after a pin that changes the
  type and adds a reason, the marketer's request shows no pin, warning or linked-record data. The
  `type` may change (it is already shown to the marketer). Run red, then green.

**Checkpoint (batch 4)**: pinning and warnings work. The full suites are green. Commit.

---

## Phase 6: User Story 4 - Rule reminders next to the buttons (Priority: P3)

**Goal**: show the 15-day reminder with the expiry or «تاريخ الانتهاء غير متوفر», and announce the
commission question on a return.

**Independent Test**: spec.md › User Story 4 › Independent Test.

- [x] T050 [P] [US4] Extend `web/src/__tests__/decisionPanel.test.tsx`. Check:
  - with an open `family_exists` reason, the reminder «إذا كان للاشتراك الأول 15 يوماً أو أكثر
    متبقية: قبول. أقل من ذلك: رفض.» is shown, with «تاريخ الانتهاء غير متوفر» when the linked
    record's `expiry` is null, and the date with «حسب آخر استيراد» when it is set;
  - a return shows «سيُطلب تحديد احتساب العمولة»;
  - a new request with only edited numbers shows neither.

  Run: **red**.
- [x] T051 [US4] Implement both reminders in `web/src/pages/admin/pending/DecisionPanel.tsx`. T050
  **green**.

---

## Phase 7: User Story 5 - Admin home counts (Priority: P3)

**Goal**: today and month counts in Baghdad time for every admin.

**Independent Test**: spec.md › User Story 5 › Independent Test.

- [x] T052 [P] [US5] Write `api/tests/integration/test_admin_home.py` with a frozen clock.
  - Data: three submissions today (one auto-approved, two pending), one of them rejected, and one
    request from earlier in the month.
  - Expect `today = {submitted: 3, approved: 1, pending: 1, rejected: 1, linked: 0}`, and `month`
    including the earlier request.
  - A submission at 23:30 Baghdad counts in that Baghdad day.
  - An admin with only `settings` gets 200, and the marketer gets 403.
  - The JSON has only numbers.

  Run: **red**.
- [x] T053 [US5] Create `api/app/services/admin_home.py` with `counts(db)`
  ([research R10](./research.md#r10-admin-home-counts-fr-021)), and add `GET /admin/home` to
  `api/app/api/admin.py` with `require_roles("super_admin", "admin")`. T052 **green**.
- [x] T054 [P] [US5] Write `web/src/__tests__/adminHome.test.tsx`: the rows «اليوم» and «هذا الشهر»
  each show مرفوعة، مقبولة، بالانتظار، تم الربط، مرفوضة. Run: **red**.
- [x] T055 [US5] Create `web/src/pages/admin/Home.tsx` (stat tiles, RTL, stacked on a phone), add
  `getHome()` to `web/src/lib/adminRequests.ts`, and replace `AdminHome` in `placeholders.tsx` and
  `router.tsx`. T054 **green**.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T056 [P] Extend `api/tests/integration/test_match_sources.py`: a request rejected through
  `POST …/reject` no longer matches its phone, national ID or family number.
- [x] T057 [P] Extend `api/tests/integration/test_require_permission.py`: every new route is refused without `review`, except
  `/admin/home` (SC-006).
- [x] T058 Write `e2e/tests/admin-review.spec.ts`. Flow:
  1. the marketer submits a family request and an edited-numbers request with the fake reader;
  2. the `review` admin accepts the family request, and the marketer sees «تمت الموافقة» and the
     username;
  3. the admin rejects with «سبب آخر» and a note, and the marketer sees the note;
  4. the admin pins a number on a third request so that it matches an existing subscriber, sees the
     red warning, and accepts after «القبول رغم التحذير؟»;
  5. the `settings` admin has no «طلبات بالانتظار» in the menu.

  The flow also runs at phone width.
- [x] T059 Run the full suites: `pytest`, `npm test`, `npm run lint`, `npm run typecheck` and
  Playwright. Fix anything red. Then take a light measurement (plan › Performance Goals, SC-001):
  with 300 synthetic pending requests from `request_factory`, the pending list and one request file
  each answer in under 1 s, and accept, reject and pin each in under 2 s, on the dev stack. Write
  the numbers in the batch report. It is a measurement, not a test that fails the suite.
- [x] T060 Run `docker compose up` and walk through [quickstart.md](./quickstart.md) › Manual
  scenarios 1–12.
- [x] T061 Write `specs/010-admin-request-review/manual-test-ar.md` in Arabic, on the pattern of 009:
  the setup (migration `0013 (head)`, the fake OTP, the users), then the steps and expected results
  for the list, the file, accept, return commission, reject reasons, pin and warning, concurrency,
  permissions, home counts and the audit.
- [x] T062 Final commit. `README.md` and `docs/system.md` §16 do not mark finished features, and
  this feature does not either.

---

## Dependencies & Execution Order

### Phase dependencies

- Phase 1 (Setup) → Phase 2 (Foundational) → the story phases.
- US1 (Phase 3) gives the file page that US2, US3 and US4 build on.
- US2 needs the `_live_check` from T016.
- US3 needs `accept` from T029 for the warning confirmation, and the DecisionPanel from T036.
- US4 needs the DecisionPanel (T036).
- US5 depends only on Phase 2 (T009) and can run in parallel with US1–US4.
- Polish comes last.

### User story dependencies

| Story | Depends on |
|---|---|
| US1 | Phase 2 |
| US2 | US1 (the file page and service) |
| US3 | US1, US2 (accept with warnings) |
| US4 | US2 (DecisionPanel) |
| US5 | Phase 2 only |

### Within each story

1. Tests first (red).
2. Service.
3. Routes (tests green).
4. Web lib.
5. Web tests (red).
6. Components (green).

## Parallel Example: Foundational

```text
T006 test_review_check.py      T008 rejection_reasons      T009 baghdad_today_bounds
        ↓
T007 review_check.py           T010 linked_records         T011 schemas + router
```

## Parallel Example: User Story 1

```text
T012 test_admin_pending_list   T013 test_admin_request_file   T014 test_admin_request_images
T019 adminRequests.ts + labels T020 adminPendingList.test     T022 LinkedRecordCard
```

## Implementation Strategy

### MVP first

Batches 1–3 (US1 + US2) clear the pending queue that 008 and 009 leave behind. That is the smallest
release that unblocks the field.

### Incremental delivery

- Batch 4 adds pinning and the warnings, the main anti-fraud tool for edited numbers.
- Batch 5 adds the reminders, the home counts, e2e and the manual test.

Each batch ends green and with a commit.

## Notes

- `card_readings` (raw) is never returned to any page, response or log, including the review file.
- The national ID, family number, phone and names never go into an audit `before`/`after` or a log
  line. The rejection note is the admin's own text and is the exception the marketer is meant to
  see.
- The «حذف مشترك» idea is a separate feature after 010 (`docs/features.md`). Nothing here deletes a
  request.
