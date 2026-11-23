---

description: "Task list for feature 009: Existing Subscriber Paths"
---

# Tasks: Existing Subscriber Paths

**Input**: Design documents from `specs/009-existing-subscriber-paths/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's rule: **each new test is run
red before its code is written**. Report red and green for every test task.

**Test rules**:
- Only synthetic data: the fake card reader and made-up numbers (for example national ID
  `199000000001`, family number `1234A5678901234567`). No real card images or subscribers.
- OTP uses `FakeOtpSender` / `OTP_FAKE_CODE`.
- Existing subscribers are inserted with the 008 factory `api/tests/helpers/requests.py`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each ends at a phase boundary and with a commit):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T012 |
| 2 | 3 (US1 return by identity) | T013–T024 |
| 3 | 4 (US2 phone: return and contact admin) | T025–T038 |
| 4 | 5–7 (US3, US4, Polish) | T039–T050 |

---

## Phase 1: Setup

- [x] T001 Add the error codes `no_return_match` (422) and `return_pending` (409) with their Arabic
  messages (contracts/api.md) in `api/app/errors.py`.
- [x] T002 [P] Write `api/tests/integration/test_migration_0011.py` on the pattern of
  `test_migration_0010.py`: the column exists, the reason constraint accepts `numbers_conflict` and
  rejects an unknown value, and downgrade/upgrade round-trips. Run: **red**.
- [x] T003 Write migration `api/migrations/versions/0011_existing_subscriber_paths.py`. It adds
  [data-model.md](./data-model.md) `drafts.return_key` and widens the check constraint on
  `request_reasons.reason` to the four values in data-model.md › request_reasons. The downgrade
  restores the 008 constraint and drops the column. Mirror both in `api/app/models/draft.py` and
  `api/app/models/request.py` (`REASONS`). T002 **green**.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the per-record match engine (research R1, R2) and the v1.10 decision table (R4). There is
no visible change yet, except that the 008 behavior stays green.

- [x] T004 [P] Write unit tests for `MatchRecord` and the views `phone`, `same_person`, `id_conflict`,
  `family` and the return target (R1, R2) in `api/tests/unit/test_matches.py`. Cover:
  - a record with every flag;
  - a record with no family (conflict);
  - a record with no national ID (family view);
  - phone A + identity B gives target {B};
  - phone only gives target = phone records;
  - nothing gives an empty target.

  Run them: **red**.
- [x] T005 Implement `MatchRecord`, the views and `return_target()` in `api/app/core/matches.py`.
  Keep the 008 properties `.phone`, `.national_id` and `.family` as views, so current callers keep
  working. T004 **green**.
- [x] T006 [P] Extend `api/tests/unit/test_decision.py` with the v1.10 rows (R4):
  - same_person without a return → `national_id_exists`;
  - id_conflict → reason `numbers_conflict`, type new, result `pending_approval`;
  - id_conflict + confirmed family → type additional, both reasons;
  - valid return (identity) → type return, reasons `return` (+ `numbers_edited`);
  - return with a phone outside the target → `phone_used`;
  - return with a pending record in the target → `return_pending`;
  - return with family-only records outside the target → `family_exists` without confirmation.

  Every 008 case stays. Run: **red**.
- [x] T007 Rewrite `decide()` in `api/app/core/decision.py` for the v1.10 table. Add the parameter
  `return_valid: bool`, refusal `return_pending`, type `return`, reasons `return` / `numbers_conflict`,
  and result `pending_approval` (data-model.md › Decision). T006 **green**.
- [x] T008 [P] Extend `api/tests/integration/test_match_sources.py`. The sijil source returns one
  record per matching request, with correct `phone` / `national_id` / `family` / `pending` flags, in
  one query; rejected requests are still ignored. Run: **red**.
- [x] T009 Change `_sijil_source` and `find_matches` in `api/app/services/match_service.py` to return
  records (one `OR` query over active statuses, flags from column comparisons, `pending` =
  `status == 'pending_review'`). Update the source docstring for 013/014. T008 **green**.
- [x] T010 Move the 008 callers to the views: `api/app/services/draft_service.py` (`draft_checks`:
  `national_id_exists` = same_person), `api/app/services/phone_checks.py`,
  `api/app/services/submit_service.py` (pass `return_valid=False` for now, and write reason rows from
  the records).
- [x] T011 Run the whole api suite. Any 008 test that expected a national-ID refusal for a match
  with a **different** family number now gets the v1.10 result (`numbers_conflict`, pending review).
  Update those tests to that expectation, run them red against the old expectation first, and
  record which ones changed. Every other test is green.
- [x] T012 Commit batch 1.

**Checkpoint**: the engine reports records, the table knows every v1.10 row, and 008 behavior is
unchanged except for the marked conflict cases.

---

## Phase 3: User Story 1 - Same person returns to service (Priority: P1) 🎯 MVP

**Goal**: the national ID and family number match the same record; the marketer chooses «طلب العودة
للخدمة» and submits a pending return. The conflict case (FR-004) is handled here too, because it
shares the identity check.

**Independent Test**: spec US1 Independent Test; quickstart scenarios 1, 4, 5.

### Tests for User Story 1

- [x] T013 [P] [US1] Write `api/tests/integration/test_return_path.py` (identity basis). Cover:
  - checks show `return_available`, `return_basis=identity`;
  - `PATCH return_chosen=true` stores `return_key` (data-model.md › drafts.return_key) and audits
    `draft.return_chosen`;
  - `false` withdraws and audits `draft.return_withdrawn`;
  - `true` with no target → 422 `no_return_match`;
  - choosing return clears `additional_confirmed` and the reverse;
  - changing the family number makes the choice stale (`return_chosen=false`), and the column is
    cleared on the next save;
  - submit → 201, type return, status pending_review, `result=pending_approval`, `return` reason rows
    with `details.basis` linked to the target;
  - username = target's username (R7);
  - a pending record in the target → 409 `return_pending`, draft kept, attempt audited;
  - a stale choice at submit falls back to `national_id_exists` / approval;
  - a return draft without the card images is refused with `draft_incomplete` (FR-008).

  Run: **red**.
- [x] T014 [P] [US1] Write `api/tests/integration/test_numbers_conflict.py`. Cover:
  - same national ID, different family → checks `id_conflict=true`, no missing item;
  - after OTP, submit → pending_review, reason `numbers_conflict` linked to the record, type new;
  - with a confirmed family match on another record as well → type additional, both reasons;
  - a matched record with no family number is also a conflict (factory row with an empty family key
    is not allowed by the 008 constraint, so cover that through a fake source registered in the
    test).

  Run: **red**.
- [x] T015 [P] [US1] Extend `api/tests/integration/test_submit_concurrency.py`: two return drafts for
  the same person submitted at once → one request, the other gets `return_pending`. Run: **red**.

### Implementation for User Story 1

- [x] T016 [US1] Add `return_chosen: bool | None` to the PATCH changes and the new fields to
  `DraftChecksOut` (data-model.md › DraftChecksOut) in `api/app/schemas/drafts.py`.
- [x] T017 [US1] In `api/app/services/draft_service.py`:
  - `return_key_for(draft, matches)`, `return_valid(draft, matches)`, `apply_return_choice()` with
    the mutual exclusion against `additional_confirmed_key`, plus audit;
  - clearing a stale key on save;
  - `draft_checks` filling the new fields;
  - `missing_items` changes (data-model.md › Missing items): `national_id_exists` and `phone_used`
    drop with a valid return, add `return_pending`, and no family confirmation is needed on a return;
  - wire into the PATCH handler in `api/app/api/drafts.py`.
- [x] T018 [US1] In `api/app/services/submit_service.py`:
  - compute `return_valid` under the locks and pass it to `decide()`;
  - handle the `return_pending` refusal like the other refusals;
  - write the `return` and `numbers_conflict` reason rows per record, with `details.basis`;
  - set the return username (R7);
  - `_result()` returns `pending_approval` for return / numbers_conflict;
  - `request.submitted` audit reasons.
- [x] T019 [US1] Add `pending_approval` to `result` in `api/app/schemas/requests.py`.
- [x] T020 [US1] Run T013–T015 → **green**, then the full api suite.
- [x] T021 [P] [US1] Write `web/src/__tests__/returnNotice.test.tsx`. Cover:
  - `national_id_exists` shows «المشترك لديه اشتراك سابق» and «طلب العودة للخدمة»;
  - pressing it saves `return_chosen: true`;
  - chosen state shows «تم اختيار طلب العودة للخدمة» and «إلغاء»;
  - `return_pending` text;
  - `id_conflict` notice text with no button.

  Run: **red**.
- [x] T022 [US1] Build the web side:
  - `web/src/pages/marketer/subscriber/ReturnNotice.tsx`;
  - show it and the conflict notice in `CardDataSection.tsx`;
  - add the check fields and `return_chosen` to `web/src/lib/drafts.ts` and
    `web/src/lib/draftFormController.ts`;
  - add the missing-item labels (contracts/api.md table) in `web/src/lib/draftValidation.ts`;
  - add `pending_approval` text and the reason/type labels in `web/src/lib/requests.ts`,
    `web/src/lib/labels.ts` and `web/src/pages/marketer/RequestResult.tsx`.

  T021 **green**, and `requestResult.test.tsx` gets a `pending_approval` case (red → green).
- [x] T023 [US1] Run `npm test` and the full api suite. Do a quick manual run of quickstart
  scenarios 1, 4, 5 with `docker compose up`.
- [x] T024 [US1] Commit batch 2.

**Checkpoint**: return by identity and the conflict case work end to end.

---

## Phase 4: User Story 2 - Phone already belongs to a subscriber (Priority: P1)

**Goal**: a used phone offers «طلب العودة للخدمة» (phone basis, OTP allowed on the target's own
phone) and «الاتصال بالإدارة» (WhatsApp to the settings number).

**Independent Test**: spec US2 Independent Test; quickstart scenarios 2, 3, 7.

### Tests for User Story 2

- [ ] T025 [P] [US2] Extend `api/tests/integration/test_return_path.py` (phone basis). Cover:
  - phone of a record and no identity match → `return_basis=phone`;
  - after choosing, `POST otp/send` to that phone succeeds;
  - without a choice it is still 409 `phone_used`;
  - phone of A + identity of B → basis identity, and OTP to A's phone gives 409;
  - submit with phone basis → `return` reason with `details.basis=phone`;
  - phone + identity on the same record → one return choice only.

  Run: **red**.
- [ ] T026 [P] [US2] Extend `api/tests/integration/test_otp.py`: the precheck exception applies only
  with a valid return choice, and a stale choice gives `phone_used` again. Run: **red**.
- [ ] T027 [P] [US2] Write `api/tests/integration/test_admin_whatsapp.py` (and add matching cases
  to `test_settings_general.py` and `test_client_config.py` where they fit better). Cover:
  - `GET/PATCH /api/admin/settings/general` with `admin_whatsapp` (data-model.md ›
    app_settings.admin_whatsapp): §8.1 normalization, invalid → 422 `invalid_phone`, empty clears,
    audit before/after, needs `settings` (403 / 404 without it, as the route does);
  - `GET /api/client-config` returns the number or null to a marketer;
  - `POST /api/drafts/{id}/contact-admin` → 204, audit `draft.contact_admin_opened` with the draft id
    only, draft version unchanged, another marketer → 404.

  Run: **red**.

### Implementation for User Story 2

- [ ] T028 [US2] Return-target exception in `precheck_for_otp`, in `api/app/services/phone_checks.py`
  (R6). T026 **green**.
- [ ] T029 [US2] Phone-basis keys and validity in `api/app/services/draft_service.py`, and in
  `submit_service.py` if anything is still missing. T025 **green**.
- [ ] T030 [US2] Add [data-model.md](./data-model.md) `app_settings.admin_whatsapp` to
  `get_general` / `update_general` in `api/app/services/settings_service.py`. Make `update_general` accept partial changes, so the OTP
  minutes and the number can be changed separately, with one audit row per changed key. Update the
  schema and route in `api/app/api/settings.py`.
- [ ] T031 [US2] Add `admin_whatsapp` to `api/app/api/client_config.py`.
- [ ] T032 [US2] Add `POST /drafts/{id}/contact-admin` to `api/app/api/drafts.py`, with owner check
  and audit. T027 **green**.
- [ ] T033 [P] [US2] Write `web/src/__tests__/contactAdmin.test.tsx`. Cover:
  - the link is `https://wa.me/9647…?text=…`;
  - the decoded text contains the marketer's name and does **not** contain the typed phone;
  - the button is an `<a target="_blank">`;
  - a click fires the contact-admin call;
  - when the number is null the button is disabled with «رقم الإدارة غير مضبوط في الإعدادات».

  Run: **red**.
- [ ] T034 [US2] Build `web/src/lib/contactAdmin.ts` and
  `web/src/pages/marketer/subscriber/ContactAdminButton.tsx`. Show `ReturnNotice` (phone basis) and
  the button in `PhoneSection.tsx`, reading `admin_whatsapp` from client config. T033 **green**.
- [ ] T035 [P] [US2] Write a Vitest test for the «رقم واتساب الإدارة» field in
  `web/src/__tests__/generalTab.test.tsx`: it saves, shows the server error, and empty clears it.
  Run: **red**.
- [ ] T036 [US2] Add the field to `web/src/pages/admin/settings/GeneralTab.tsx`, and the audit label
  for `draft.contact_admin_opened` / return actions in `web/src/lib/labels.ts`. T035 **green**.
- [ ] T037 [US2] Run the full api suite and `npm test`. Do a manual run of quickstart scenarios 2, 3, 7.
- [ ] T038 [US2] Commit batch 3.

**Checkpoint**: both return bases and the contact button work.

---

## Phase 5: User Story 3 - Second subscription for the same family (Priority: P2)

**Goal**: the 008 family path, relabeled. A national ID that differs (or is missing on a legacy
record) leads to the family path.

- [ ] T039 [P] [US3] Update `web/src/__tests__/familyMatchNotice.test.tsx` to expect «إضافة اشتراك
  ثاني». Run: **red**.
- [ ] T040 [US3] Rename the button and the missing-item label in
  `web/src/pages/marketer/subscriber/FamilyMatchNotice.tsx` and `web/src/lib/draftValidation.ts`.
  T039 **green**.
- [ ] T041 [P] [US3] Add a case to `api/tests/integration/test_submit.py` (red first if new): a
  family-only match on a record without a national ID (fake source) gives type additional with
  confirmation, as 008.

---

## Phase 6: User Story 4 - Start from the dashboard (Priority: P3)

- [ ] T042 [P] [US4] Write `web/src/__tests__/dashboard.test.tsx`: «إضافة اشتراك لمشترك موجود» is
  enabled, has no «قريباً», and creates a draft and opens the form like «إضافة مشترك جديد». Run:
  **red**.
- [ ] T043 [US4] Enable the button in `web/src/pages/marketer/Dashboard.tsx`, sharing the new-draft
  handler. T042 **green**.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T044 [P] Write `api/tests/integration/test_marketer_privacy.py` (SC-003). For every path (return
  identity, return phone, conflict, family, pending block, contact-admin), collect every response
  body the marketer gets (draft GET/PATCH, otp/send, submit, request GET/list). Assert that none
  contains the matched record's name, phone, username, tower code, national ID, family number,
  request number or id. This checks a design already built, so it may pass on its first run; to
  prove it can fail, run it once against a deliberately leaking response, then green.
- [ ] T045 [P] Extend `api/tests/integration/test_log_safety.py` and
  `api/tests/integration/test_audit_completeness.py`. The new actions (`draft.return_chosen`,
  `draft.return_withdrawn`, `draft.contact_admin_opened`) and the new submit reasons hold no card
  data or phone, and every one is recorded. Red first for the completeness case.
- [ ] T046 Write `e2e/tests/existing-subscriber.spec.ts`: a return by identity to the result screen,
  and a return by phone to the result screen (fake OTP). Run red, then green.
- [ ] T047 [P] Write the Arabic manual test guide
  `specs/009-existing-subscriber-paths/manual-test-ar.md` from quickstart scenarios 1–9.
- [ ] T048 Check that `docs/system.md` v1.10 matches the built behavior (the §6.1 rows, §6.3, §10
  settings). Fix the document if a detail moved during the build.
- [ ] T049 Run everything: full api suite, `npm test`, Playwright (`existing-subscriber.spec.ts`,
  `submit.spec.ts`, `otp.spec.ts`), and `docker compose up` with a smoke run of the quickstart.
- [ ] T050 Commit batch 4.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 (blocks all stories).
- US1 (Phase 3) needs Phase 2. US2 needs US1's return choice (T016–T018) and adds the phone basis.
- US3 and US4 depend only on Phase 2 and can go in any order after it. They are scheduled in batch
  4 to keep the batches small.
- Polish runs last.
- Within a phase: tests (red) → schemas/models → services → routes → web → full run → commit.

## Parallel Example: Foundational

```text
T004 test_matches.py   |  T006 test_decision.py  |  T008 test_match_sources.py   (all red together)
then T005 → T007 → T009 → T010 → T011
```

## Implementation Strategy

1. Batch 1: per-record engine and decision table, with 008 kept green (except the marked conflict
   cases).
2. Batch 2: return by identity, the conflict case, result text (the MVP).
3. Batch 3: phone return and «الاتصال بالإدارة» with its setting.
4. Batch 4: relabel, dashboard, privacy and log checks, e2e, manual guide.
