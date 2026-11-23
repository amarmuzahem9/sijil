---

description: "Task list for feature 008: Request Check and Decision at Submission"
---

# Tasks: Request Check and Decision at Submission

**Input**: Design documents from `specs/008-submission-decision/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII. Every §6.1 row, every combination, the
comparison keys, the transitions and the concurrency rule need tests. Write each test task first
and confirm it fails.

**Test rules**:
- Only synthetic data: the fake card reader and made-up numbers. No real card images or subscribers.
- OTP uses `FakeOtpSender` / `OTP_FAKE_CODE`.
- Tests that need an existing subscriber insert a `requests` row through a factory in
  `api/tests/helpers/requests.py`. 010 has no reject screen yet, so rejected rows also come from the factory.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each ends at a phase boundary):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T016 |
| 2 | 3–4 (US1, US2) | T017–T032 |
| 3 | 5–8 (US3–US6) | T033–T044 |
| 4 | 9 (Polish) | T045–T051 |

---

## Phase 1: Setup

- [x] T001 Add the new error codes and their Arabic messages to `api/app/errors.py`, as listed in
  contracts/api.md:
  - `phone_used` (409)
  - `national_id_exists` (409)
  - `no_family_match` (422)
  - `draft_incomplete` (422)
  - `otp_needs_reverify` (409)
  - `catalog_changed` (409)
  - `request_not_found` (404)
- [x] T002 [P] Add `request_factory(db, **overrides)` to `api/tests/helpers/requests.py`. It inserts a
  valid `requests` row with synthetic values and any status, and takes the next number from the
  sequence. Reuse the existing user and catalog fixtures.

---

## Phase 2: Foundational (blocking prerequisites)

**⚠️ No user story work can begin until this phase is complete.**

### Tests first

- [x] T003 [P] Create `api/tests/fixtures/family_key_cases.json` and
  `api/tests/unit/test_family_key.py` (research R3). Cases:
  - lower case;
  - spaces and dashes;
  - Arabic-Indic digits;
  - `O` at every position, including the series letter;
  - odd lengths kept;
  - empty or symbols only → `None`.
- [x] T004 [P] Create `api/tests/unit/test_decision.py` (research R2):
  - each row alone;
  - row 1 beats rows 2–4;
  - row 2 beats rows 3–4;
  - rows 3+4 → both reasons and type `additional`;
  - no match and no edit → approved;
  - reasons are listed in a stable order.
- [x] T005 [P] Create `api/tests/unit/test_numbers_edited.py` (research R4, FR-005a):
  - equal to the front reading → not edited;
  - equal to a verified MRZ → not edited;
  - an Arabic-digit form of the reading → not edited;
  - a different digit → edited;
  - no `card_fields` entry, or `original` null → edited;
  - each field is reported in `fields`.
- [x] T006 [P] Create `api/tests/integration/test_match_sources.py` (FR-001, FR-002, FR-005):
  - a phone written `+964 780…`, a national ID in Arabic digits, and a family number with lower
    case or `O` all match a factory request;
  - `rejected` requests never match;
  - `pending_review`, `approved` and `linked` match;
  - another marketer's draft never matches;
  - `exclude` skips nothing that matters in 008 (there is no self-request).
- [x] T007 [P] Create `api/tests/integration/test_migration_0010.py`. It upgrades and downgrades
  `0010`, and checks that the CHECK constraints refuse:
  - a bad `data-model.md` `Request.status`;
  - a bad `Request.type`;
  - a bad `Request.phone`, `Request.national_id` and `Request.family_key`;
  - an `approved` row without `Request.approved_at`;
  - a bad `RequestReason.reason`.

### Implementation

- [x] T008 Create the migration `api/migrations/versions/0010_requests.py` from data-model.md:
  - the sequence `request_number_seq START 1001`;
  - the tables `requests`, `request_reasons` and `request_images`, with every column, CHECK, index
    and FK as listed. They cover the constrained fields `Request.number`, `Request.draft_id`,
    `Request.type`, `Request.status`, `Request.no_surname`, `Request.national_id`,
    `Request.family_key`, `Request.phone`, `Request.approved_at`, `Request.area_id`,
    `Request.tower_id`, `Request.plan_id`, `RequestReason.reason`, `RequestImage.side` and
    `RequestImage.request_id`. Also cite and create, from data-model.md: `Request.marketer_id`,
    the nine name fields (`Request.first_name` … `Request.mother_surname`, 7 NOT NULL, 2 nullable),
    `Request.full_name`, `Request.national_id_input`, `Request.family_number`, the back fields
    (`Request.birth_date` … `Request.issuing_authority`), `Request.card_fields`,
    `Request.national_id_check`, `Request.card_readings`, `Request.location_lat`,
    `Request.location_lng`, `Request.location_source`, `Request.location_accuracy_m`,
    `Request.address`, `Request.landmark`, the copies (`Request.area_name` … `Request.second_price`),
    `Request.username`, `Request.otp_verified_at`, `Request.submitted_at`, `Request.approved_by`,
    `RequestReason.request_id`, `RequestReason.matched_source`, `RequestReason.matched_ref`,
    `RequestReason.details`, the `request_reasons` unique key (`UNIQUE NULLS NOT DISTINCT`),
    `RequestImage.id`, `RequestImage.file_name`, `RequestImage.uploaded_by`;
  - the column `drafts.additional_confirmed_key` (data-model.md `Draft.additional_confirmed_key`);
  - a downgrade that drops everything.
- [x] T009 [P] Create the models `Request`, `RequestReason` and `RequestImage` in
  `api/app/models/request.py`, mirroring 0010. Export them from `api/app/models/__init__.py`.
  Add `additional_confirmed_key` to `api/app/models/draft.py`.
- [x] T010 [P] Implement `family_key(text) -> str | None` in `api/app/core/family_key.py`
  (research R3).
- [x] T011 [P] Implement the pure `decide(matches, edited_fields, additional_confirmed) -> Decision`
  in `api/app/core/decision.py` (research R2).
  - `Decision` holds `refusal`, `type`, `status`, `reasons` and `result`.
  - `result` is `approved`, `pending_family` or `pending_review`, as contracts/api.md defines it.
- [x] T012 Implement `api/app/services/match_service.py` (research R2):
  - `MatchRef` and `Matches`;
  - `register_source`, `unregister_source` and `find_matches(db, *, phone, national_id, family_key)`;
  - the `sijil` source, which queries `requests` where `status IN ('pending_review','approved','linked')`;
  - a `None` key never queried.
- [x] T013 Implement `edited_fields(draft) -> list[str]` in `api/app/services/numbers_edited.py`
  (research R4). It compares with `card_fields[*].original` and `national_id_check.mrz`, using
  `normalize_national_id` and `family_key`.
- [x] T014 Add the early checks to `api/app/services/draft_service.py` (research R5, R12; contracts
  api.md › DraftOut):
  - `draft_checks(db, draft)` builds `checks` with `phone_used`, `national_id_exists`,
    `family_exists` and `additional_confirmed`;
  - `to_out` gains a `db` argument and inserts the missing items `national_id_exists`,
    `family_exists_unconfirmed` and `phone_used` after `national_id`, `family_number` and `phone`;
  - every caller of `to_out` and `missing_count` (in `api/app/api/drafts.py`, `otp_service` and
    `card_reading_service`) is updated;
  - `missing_count` in `list_own` also counts them.
- [x] T015 [P] Add `checks: DraftChecksOut` to `DraftOut` in `api/app/schemas/drafts.py`, and the
  new schemas `SubmitIn`, `RequestOut` and `RequestListItem` in `api/app/schemas/requests.py`, as
  in contracts/api.md. `username` is null unless the status is approved or linked.
- [x] T016 Register usage checks for `area`, `tower` and `plan` that count `requests` of any status
  (research R9). Put them in `api/app/services/match_service.py` or a module imported at startup,
  using `settings_service.register_usage_check`. Extend `api/tests/integration/test_settings_areas_towers.py`
  and `api/tests/integration/test_settings_plans.py`: an item used by a factory request cannot be deleted.

**Checkpoint**: T003–T007 pass. Draft responses carry `checks`.

---

## Phase 3: User Story 1 - Submit a clean new request and get instant approval (Priority: P1) 🎯 MVP

**Goal**: A complete, verified, clean draft becomes request `T3C-1001`, approved, with a username.

**Independent Test**: quickstart scenario 1.

### Tests for User Story 1

- [x] T017 [P] [US1] Create `api/tests/integration/test_submit.py` with the clean path (FR-011 to
  FR-019, FR-021):
  - The first submit returns 201 with number 1001, `T3C-1001`, type `new`, status `approved`,
    `approved_at = submitted_at`, `approved_by` null, the username `ALM03-07…` and
    `result=approved`.
  - The draft row and its `draft_images` and `card_readings` rows are gone.
  - The `request_images` rows keep the same ids and file names, and the files exist on disk.
  - `card_readings` is copied, and `otp_verified_at` is copied.
  - Changing the plan price afterwards leaves the request's prices unchanged.
  - The second request gets 1002.
- [x] T018 [P] [US1] Add the refusal cases to `api/tests/integration/test_submit.py`:
  - a missing item → 422 `draft_incomplete` with `missing`;
  - an expired card (clock override) → 422;
  - an unconfirmed national ID → 422;
  - a context change after verification → 409 `otp_needs_reverify`;
  - a stale `version` → 409 `draft_conflict`;
  - a deactivated plan → 409 `catalog_changed`, and the choice is cleared;
  - another marketer → 404;
  - an admin, or a stopped or archived marketer → 403 `forbidden`;
  - in every refusal, the draft stays unchanged and no request exists.
- [x] T019 [P] [US1] Add the idempotent case to `api/tests/integration/test_submit.py` (FR-013):
  repeating the submit returns 200 with the same request, and the number is not consumed.
- [x] T020 [P] [US1] Create `api/tests/integration/test_requests_api.py`:
  - `GET /api/requests` returns own requests only, newest first, and filters by `status`;
  - `GET /api/requests/{id}` of another marketer → 404 `request_not_found`;
  - no response contains `card_readings`.

### Implementation for User Story 1

- [x] T021 [US1] Implement `submit(db, user, draft_id, version)` in
  `api/app/services/submit_service.py`, following research R6 steps 1–8 and R8:
  - lock the draft `FOR UPDATE`;
  - run `refresh_copies`; on `catalog_changed` commit the cleared choice (which also clears the
    verification) before returning 409, while the row 1 and row 2 refusals roll back everything;
  - check the missing items and the OTP context (`otp_service.context_hash`);
  - take the advisory locks in a fixed order;
  - run `find_matches`, `edited_fields` and `decide`;
  - call `nextval`;
  - insert the request (copying every data-model.md `Request.*` field) and the `RequestReason` rows;
  - move the image rows to `RequestImage`;
  - delete the draft;
  - audit `request.submitted` (R13);
  - log one safe line.
- [x] T022 [US1] Include the `request_images.file_name` values in
  `draft_service.referenced_file_names` (`api/app/services/draft_service.py`), so the orphan sweep
  keeps request files. Extend `api/tests/integration/test_draft_images.py` with a case where the
  sweep keeps a submitted request's file.
- [x] T023 [US1] Add `POST /api/drafts/{id}/submit` to `api/app/api/drafts.py` (201 or 200). Create
  `api/app/api/requests.py` with `GET /api/requests` and `GET /api/requests/{id}`, owner-only, and
  add `requests` to the router tuple in `api/app/main.py`.
- [x] T024 [P] [US1] Create `web/src/lib/requests.ts`:
  - `submitDraft(id, version)`, `listRequests(status?)` and `getRequest(id)`;
  - the error-code → Arabic map from contracts/api.md;
  - `numberLabel` and `resultText`.
- [x] T025 [US1] Enable «إرسال» in `web/src/pages/marketer/subscriber/MissingSummary.tsx` when
  `missing` is empty and `otp.status === 'verified'`. On press:
  - flush autosave;
  - submit with the current version;
  - navigate to `/requests/:id`;
  - on an error, show its Arabic text and reload the draft.

  Update the header comment.
- [x] T026 [P] [US1] Create `web/src/pages/marketer/RequestResult.tsx` and add the route
  `/requests/:id`:
  - approved: «تمت الموافقة», the number and the username, with «نسخ اليوزر» (clipboard);
  - `pending_family`: «بانتظار موافقة المسؤول»;
  - `pending_review`: «طلبك بانتظار التدقيق»;
  - the status chip uses `STATUS_COLORS`.
- [x] T027 [US1] Fill the «بالانتظار» and «مقبولة» tabs in `web/src/pages/marketer/Requests.tsx` from
  `listRequests`. Each row shows the number, name, Baghdad date and status color, and opens
  `/requests/:id`. Open «بالانتظار» by default when requests exist (research R11).
- [x] T028 [P] [US1] Create `web/src/__tests__/missingSummarySubmit.test.tsx` and
  `web/src/__tests__/requestResult.test.tsx`:
  - the button is enabled only when the draft is complete and verified;
  - the three result texts;
  - the username is hidden when the request is not approved.

**Checkpoint**: quickstart scenarios 1, 8, 9 and 10 pass.

---

## Phase 4: User Story 2 - A used phone is stopped before any code is sent (Priority: P1)

**Goal**: Row 1, both at «تحقّق» and at submission.

**Independent Test**: quickstart scenario 2.

### Tests for User Story 2

- [x] T029 [P] [US2] Extend `api/tests/integration/test_otp.py` with a used phone from a factory
  request, written in another form:
  - send → 409 `phone_used`;
  - the fake sender gets no call;
  - no `otp_challenges` row is added;
  - a later send with a free phone is not delayed by the 60 s wait.
- [x] T030 [P] [US2] Add submit cases to `api/tests/integration/test_submit.py`:
  - a phone taken after verification → 409 `phone_used`, the draft is kept, and
    `request.submit_refused` is audited with `{reason}` only;
  - a used phone plus a family match → still `phone_used` (§6.1 note 1).
- [x] T031 [P] [US2] Create `api/tests/integration/test_submit_concurrency.py` (SC-004): 20 threads,
  each with its own verified draft and the same phone, submit at once. Exactly one 201 and 19
  `phone_used`. Repeat with the same national ID.

### Implementation for User Story 2

- [x] T032 [US2] Implement `precheck_for_otp` in `api/app/services/phone_checks.py` with
  `find_matches(phone=…)` (research R10), returning `AppError("phone_used", 409)`. Update its
  docstring. Show `phone_used` in `web/src/pages/marketer/subscriber/PhoneSection.tsx` and
  `OtpControl.tsx`, with the message from contracts/api.md, and map it in `web/src/lib/otp.ts`.

**Checkpoint**: quickstart scenario 2 passes. Batch 2 ends here.

---

## Phase 5: User Story 3 - Same person already subscribed is blocked as new (Priority: P1)

**Goal**: Row 2, as a warning and as a refusal.

**Independent Test**: quickstart scenario 3.

- [x] T033 [P] [US3] Add to `api/tests/integration/test_submit.py`:
  - the national ID exists (Arabic digits) → the draft response has the missing item
    `national_id_exists`;
  - submit with that match (whether seen on the page or new since the last save) → 409
    `national_id_exists` (rows 1–2 refuse with their own code, research R6 step 7), the draft is
    kept, no number is used, and the refusal is audited;
  - a rejected request with the same national ID → approved (Q1).
- [x] T034 [US3] Show the `national_id_exists` message under the national ID in
  `web/src/pages/marketer/subscriber/CardDataSection.tsx`, with no button (FR-009). (The labels of
  the three server-only items were added in batch 2, as `SERVER_ITEMS` in `MissingSummary.tsx`, so
  the shared 005 order fixture stays unchanged.)

---

## Phase 6: User Story 4 - Family already subscribed goes to admin approval (Priority: P2)

**Goal**: Row 3 with the «طلب اشتراك إضافي» confirmation.

**Independent Test**: quickstart scenario 4.

- [x] T035 [P] [US4] Add to `api/tests/integration/test_drafts_autosave.py`:
  - PATCH `additional_confirmed: true` with a family match stores
    `Draft.additional_confirmed_key` (data-model.md);
  - without a match → 422 `no_family_match`;
  - changing the family number drops the confirmation (`checks.additional_confirmed` false, and
    the missing item `family_exists_unconfirmed` is back).
- [x] T036 [P] [US4] Add to `api/tests/integration/test_submit.py`: a confirmed family match → 201,
  type `additional`, `pending_review`, `result=pending_family`, and one `request_reasons` row
  `family_exists` with `matched_source=sijil` and `matched_ref` = the old request id; two matches
  → two rows.
- [x] T037 [US4] Accept `additional_confirmed` in the PATCH changes (`api/app/schemas/drafts.py`,
  `api/app/services/draft_service.py`), following research R12.
- [x] T038 [P] [US4] Create `web/src/pages/marketer/subscriber/FamilyMatchNotice.tsx` (message +
  «طلب اشتراك إضافي» → PATCH, then the confirmed state) and place it under the family number in
  `CardDataSection.tsx`. Create `web/src/__tests__/familyMatchNotice.test.tsx`.

---

## Phase 7: User Story 5 - Edited numbers go to review (Priority: P2)

**Goal**: Row 4, including hand-typed numbers (Q3).

**Independent Test**: quickstart scenarios 5 and 6.

- [x] T039 [P] [US5] Add to `api/tests/integration/test_submit.py`. Use the fake card reader where
  a scenario needs a reading.
  - a family number changed from the reading → `pending_review`, reason `numbers_edited` with
    `{"fields": ["family_number"]}`, `result=pending_review`;
  - only a name edited → approved;
  - a number typed with no reading → `numbers_edited`;
  - the MRZ value chosen in a 006 mismatch → approved;
  - a family match plus an edit → both reasons, type `additional`, `result=pending_family`.
- [x] T040 [US5] Confirm `submit_service` writes the `numbers_edited` reason with `details.fields`
  from `edited_fields`. Fix any gap found by T039 in `api/app/services/submit_service.py`.

---

## Phase 8: User Story 6 - Early warnings while filling the form (Priority: P3)

**Goal**: Warnings show up without revealing the other subscriber.

**Independent Test**: spec User Story 6.

- [x] T041 [P] [US6] Create `api/tests/integration/test_draft_checks.py`:
  - for each key, a match shows in `checks` and `missing` after PATCH, PUT and GET;
  - clearing the value removes it;
  - the response JSON contains none of the matched request's name, username, tower, phone or ids
    (SC-006).
- [x] T042 [P] [US6] Add a case to `api/tests/integration/test_card_reading.py`: a national ID filled
  by the fake reader that matches an existing request produces `national_id_exists` in the draft
  the page loads when the reading finishes (the status poll itself carries no draft).
- [x] T043 [US6] In `web/src/pages/marketer/subscriber/SubscriberForm.tsx` (or the section
  components), refresh the warnings from every draft response, card-reading completion included.
  When `checks` is missing (an older server), show nothing.
- [x] T044 [P] [US6] Add Vitest cases for the warning placement in
  `web/src/__tests__/missingSummarySubmit.test.tsx`: the three items appear in page order.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T045 [P] Extend `api/tests/integration/test_log_safety.py` with a submission and a refusal. No
  national ID, family number, full phone, name or OTP code may appear in the captured logs or in
  `audit_log.after`.
- [ ] T046 [P] Extend `api/tests/integration/test_audit_completeness.py` with
  `request.submitted` and `request.submit_refused`. Add their Arabic labels to `web/src/lib/labels.ts`
  (for example «إرسال طلب» and «رفض إرسال طلب»).
- [ ] T047 [P] Create `e2e/tests/submit.spec.ts`:
  - fill a draft with the fake reader, verify with `246810`, submit, and see «تمت الموافقة», the
    number and the username;
  - a second draft with the same phone → «تحقّق» shows the used-phone message.
- [ ] T048 [P] Update `web/src/lib/requestStatus.ts` and `Requests.tsx` comments that still say «no
  request exists before 008», and update the `phone_checks.py` docstring.
- [ ] T049 Run the full suite in the containers (`pytest`, `npm test`, `npx playwright test`) and fix
  any failure. Then run `docker compose up` and walk through quickstart scenarios 1–11.
- [ ] T050 Write `specs/008-submission-decision/manual-test-ar.md`: the Arabic manual-test steps for
  the owner, covering quickstart 1–11 and the note that a failed card reading sends requests to review.
- [ ] T051 Mark the tasks done in this file, and add a short «008» note to the 007 data-model remark
  that said the draft row becomes the request. That remark should now point to 008 research R1.

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**, which blocks every story.
- **US1** (Phase 3) is first: the submit service is used by US2–US5 tests.
- **US2 and US3** depend on US1 (submit). Within them, the precheck (T032) is independent of submit.
- **US4 and US5** depend on US1. US4 T037 is independent of US5.
- **US6** depends on T014 only.
- **Polish** comes last.

### Parallel opportunities

- **Phase 2**: T003–T007 (tests) together; then T009, T010 and T011 together.
- **US1**: T017–T020 (tests) together; T024 and T026 (web) alongside T021–T023 (api).
- **US2**: T029, T030 and T031 together.
- **US4/US5/US6**: their test tasks can run together once US1 is done.

## Parallel Example: Foundational

```text
T003 test_family_key   T004 test_decision   T005 test_numbers_edited   T006 test_match_sources   T007 test_migration_0010
then: T009 models   T010 family_key   T011 decision
```

## Implementation Strategy

### MVP

Phases 1–3 deliver US1: a clean draft is submitted and approved, and the marketer sees the username.
Phase 4 (US2) closes the most expensive gap, a code sent to a used phone. Release both together.

### Incremental delivery

1. Batch 1: foundations (engine, keys, migration), with no visible change except `checks`.
2. Batch 2: submit and the used phone.
3. Batch 3: national ID, family, edited numbers, warnings.
4. Batch 4: logs, audit, e2e, manual test.
