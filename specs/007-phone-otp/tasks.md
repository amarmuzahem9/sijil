---

description: "Task list for feature 007: Subscriber Phone Verification by WhatsApp OTP"
---

# Tasks: Subscriber Phone Verification by WhatsApp OTP

**Input**: Design documents from `specs/007-phone-otp/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md),
[contracts/otp-sender.md](./contracts/otp-sender.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner. The owner's list is: expiry,
3 attempts, hourly limit, cancellation on context change, and failed send not counted. Write each
test task first and confirm it fails.

**Test rules**:
- All OTP tests use `FakeOtpSender` and the `timeutil` clock override. No test calls OTPIQ.
- No real subscriber data.
- The only real send is the owner's manual check with the dev key in `OTPIQ_API_KEY`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each ends at a phase boundary):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T012 |
| 2 | 3–4 (US1, US2) | T013–T027 |
| 3 | 5–7 (US3, US4, Polish) | T028–T040 |

---

## Phase 1: Setup (configuration)

- [x] T001 Add the OTP settings to `api/app/config.py` (research R8, contracts/otp-sender.md):
  - New settings: `otp_mode: Literal["otpiq","fake"] = "otpiq"`, `otpiq_api_key: str = ""`
    (env `OTPIQ_API_KEY`), `otpiq_base_url: str = "https://api.otpiq.com/api"`, and
    `otp_fake_code: str = ""` (6 digits or empty).
  - A validator refuses `otp_fake_code` unless `otp_mode == "fake"`.
  - `_refuse_weak_config` refuses `otp_mode == "fake"` or a non-empty `otp_fake_code` when
    staging or production. Its message gives the names only.
- [x] T002 [P] Add `OTP_MODE=otpiq`, `OTPIQ_API_KEY=` (empty, with a comment: `sk_dev_…` for
  local/staging, `sk_live_…` for production) and `OTPIQ_BASE_URL=https://api.otpiq.com/api` to
  `.env.example`. Never put a real value there.
- [x] T003 [P] Add `OTP_MODE: fake` and `OTP_FAKE_CODE: "246810"` to the `api` service in
  `docker-compose.e2e.yml`, and set `OTP_MODE=fake` in the test environment used by
  `api/tests/conftest.py`.

---

## Phase 2: Foundational (blocking prerequisites)

**⚠️ No user story work can begin until this phase is complete.**

### Tests first

- [x] T004 [P] Write the rule tests in `api/tests/unit/test_otp_rules.py`:
  - `generate_code()` always gives 6 ASCII digits, and returns `otp_fake_code` when it is set.
  - `code_hash(challenge_id, code)` is deterministic, depends on the challenge id, and does not
    contain the code (research R3).
  - `verify_code_hash` uses constant-time comparison and accepts only the right code.
  - `context_hash` changes when any one of the phone, `tower_id`, `plan_id`, `trial_price` or
    `second_price` changes, and is the same for equal values; `None` is treated as empty
    (research R4).
  - `normalize_code_entry("١٢٣ ٤٥٦") == "123456"`. 5 or 7 digits and letters give `None`.
  - `mask_phone("07801234567") == "0780****567"`.
- [x] T005 [P] Write the adapter tests in `api/tests/integration/test_otpiq_sender.py`, with
  `httpx.MockTransport` (research R2, contracts/otp-sender.md):
  - The request goes to `POST {base}/sms` with the Bearer header and the body `phoneNumber=9647…`,
    `smsType=verification`, `verificationCode`, `provider=whatsapp`.
  - The recorded real 200 body (research R2) gives `SendReceipt(provider_id="sms-…", cost=25)`.
  - The errors map to their reasons: 400 insufficient credit and spending threshold →
    `no_credit`; 400 trial mode → `rejected`; 400 unknown → `rejected`; 401 → `not_configured`;
    429 with `waitMinutes` → `busy` with its minutes; 500, timeout and connection error →
    `unavailable`.
  - An empty key raises `not_configured` without any request.
  - Captured logs never contain the code, the full phone, or the key.

### Implementation

- [x] T006 Write `api/app/core/otp.py` to pass T004:
  - `generate_code`, `code_hash`, `verify_code_hash`, `context_hash(phone, tower_id, plan_id,
    trial_price, second_price)`, `normalize_code_entry`, `mask_phone`.
  - Constants: `RESEND_WAIT = 60 s`, `HOURLY_WINDOW = 60 min`, `HOURLY_MAX = 5`,
    `MAX_ATTEMPTS = 3`.
  - The HMAC key is derived from `jwt_secret` (research R3).
- [x] T007 Write `api/app/services/otp_sender.py` to pass T005:
  - `OtpSendError`, `SendReceipt`, the `OtpSender` Protocol, `OtpiqSender`, and `FakeOtpSender`
    (`outbox`, `fail_with`, `wait_minutes`).
  - `get_otp_sender()` picks the sender from `otp_mode`, following the `get_card_reader()` pattern.
  - Provider timeout is 10 s. No body is ever logged.
- [x] T008 Write the migration `api/migrations/versions/0009_otp.py`:
  - Table: data-model.md › `otp_challenges`, with every column, the FK
    `otp_challenges.request_id → drafts.id ON DELETE SET NULL`, the checks on
    `otp_challenges.phone` and `otp_challenges.attempts`, and both indexes.
  - Draft columns: data-model.md › `drafts.otp_verified_at` and `drafts.otp_context_hash`, with
    their pair check.
  - Include a downgrade.
- [x] T009 [P] Add the `OtpChallenge` model in `api/app/models/otp.py`, matching data-model.md ›
  `otp_challenges` (`id`, `request_id`, `phone`, `code_hash`, `context_hash`, `expires_at`,
  `attempts`, `verified_at`, `created_at`). Export it from `api/app/models/__init__.py`.
- [x] T010 [P] Add `otp_verified_at` and `otp_context_hash` to `Draft` in
  `api/app/models/draft.py` (data-model.md › `drafts.otp_verified_at`, `drafts.otp_context_hash`),
  with the pair `CheckConstraint`.
- [x] T011 [P] Add the error codes and Arabic messages from contracts/api.md to `MESSAGES` in
  `api/app/errors.py`:
  - `invalid_phone`, `otp_already_verified`, `otp_resend_wait`, `otp_hourly_limit`,
    `otp_provider_busy`, `otp_not_configured`, `otp_no_credit`, `otp_rejected`,
    `otp_unavailable`, `otp_code_format`, `otp_wrong`, `otp_cancelled`, `otp_expired`,
    `otp_no_active`.
  - `otp_hourly_limit`, `otp_provider_busy` and `otp_wrong` messages that include minutes or
    attempts are built in the service and passed as `message`.
- [x] T012 [P] Add `services/phone_checks.py::precheck_for_otp(db, draft, phone) -> AppError | None`
  in `api/app/services/phone_checks.py`. It returns `None` now. Its docstring says 008 adds
  «الهاتف مستخدم» here (research R9).

**Checkpoint (end of batch 1)**: migration applies and downgrades; T004 and T005 pass; the whole
existing suite stays green.

---

## Phase 3: User Story 1 - Send a code and verify the phone (Priority: P1) 🎯 MVP

**Goal**: «تحقّق» sends a real WhatsApp code, and the right code gives ✓ «تم التحقق».

**Independent Test**: In tests, send with the fake sender, read the code from `outbox`, verify it,
and get `otp.status = "verified"`. Manually: the same with the dev key and the owner's phone.

### Tests for User Story 1

- [x] T013 [P] [US1] Write the send and verify flow tests in `api/tests/integration/test_otp.py`:
  - **Send**:
    - A send creates one challenge, and `outbox` holds the normalized phone and a 6-digit code.
    - The response `otp` is `sent` with `phone`, `resend_at`, `expires_at` and
      `attempts_left = 3`.
    - The response body contains no code.
  - **Verify**:
    - The right code gives `verified`, with `drafts.otp_verified_at` and
      `drafts.otp_context_hash` set and the version incremented.
    - Arabic-Indic digits are accepted.
  - **Refusals**:
    - An invalid phone gives 422 `invalid_phone` with no send and no row.
    - An empty phone gives `invalid_phone`.
    - Sending when already verified gives 409 `otp_already_verified`.
  - **Access and hook**:
    - Another marketer's draft gives 404 on both routes.
    - The pre-send hook is called, and an `AppError` it returns stops the send (monkeypatch it).
- [x] T014 [P] [US1] Write the component tests in `web/src/__tests__/otpControl.test.tsx`:
  - The button is disabled for an empty phone.
  - The states show «تم التحقق» with ✓, the code box with `inputMode="numeric"` and
    `autocomplete="one-time-code"`, and «يحتاج تحقق جديد».
  - The countdown text «إعادة الإرسال بعد N ثانية» counts down from `resend_at` and then turns
    into «إعادة الإرسال».
  - A pasted Arabic-digit code is accepted.

### Implementation for User Story 1

- [x] T015 [US1] Write `api/app/services/otp_service.py`:
  - `context_hash(draft)`, a wrapper over `core.otp.context_hash`.
  - `status(db, draft) -> OtpStatusOut`, deriving the status as in data-model.md › "Derived
    state" and › `DraftOut.otp`.
  - `send(db, user, draft_id, sender)`:
    1. normalize the phone;
    2. run `precheck_for_otp`;
    3. take the two advisory locks (R6);
    4. check `otp_already_verified`;
    5. call the sender;
    6. insert `OtpChallenge` with `expires_at` from `settings_service` `otp_validity_minutes`;
    7. log one masked line with `provider_id` and `cost` (R10).
  - `verify(db, user, draft_id, code)`:
    - normalize the entry;
    - lock the newest challenge `FOR UPDATE`;
    - check active and context;
    - compare the hash;
    - on success set `verified_at` and the two draft columns.
- [x] T016 [US1] Add `OtpStatusOut` and `OtpVerifyIn` to `api/app/schemas/drafts.py`, and add
  `otp: OtpStatusOut` to `DraftOut` (contracts/api.md). `draft_service.to_out` fills it through
  `otp_service.status` in `api/app/services/draft_service.py`.
- [x] T017 [US1] Add `POST /drafts/{draft_id}/otp/send` and `POST /drafts/{draft_id}/otp/verify` to
  `api/app/api/drafts.py`:
  - Both use the existing owner and client-id dependencies and return `DraftOut`.
  - Map `OtpSendError` reasons to the contracts/api.md codes.
- [x] T018 [US1] Add `otp_enabled` to `GET /api/client-config` in `api/app/api/client_config.py`.
  It is false when the mode is `otpiq` and the key is empty. Extend
  `api/tests/integration/test_client_config.py`.
- [x] T019 [P] [US1] Write `web/src/lib/otp.ts`:
  - `sendOtp(draftId)` and `verifyOtp(draftId, code)` over the existing API client.
  - The `OtpStatus` type.
  - Error code → Arabic text, using the server's `message` when present.
  - `normalizeCodeEntry` (Arabic-Indic digits, spaces).
  - Add `otp` to the draft type in `web/src/lib/drafts.ts`.
- [x] T020 [US1] Write `web/src/pages/marketer/subscriber/OtpControl.tsx`:
  - The «تحقّق» button, the code box (6 digits, numeric keypad, one-time-code, paste), the «تأكيد»
    button, the countdown and the status chip.
  - Before `sendOtp` it awaits the autosave flush, so the server has the typed phone (contracts
    › note).
  - On success it takes the returned `DraftOut` into the autosave state, so there is no version
    conflict.
  - After a send it shows «أُرسل رمز التحقق عبر الواتساب إلى 07XXXXXXXXX» (spec US1).
  - It shows «خدمة التحقق غير مهيّأة» when `otp_enabled` is false.
- [x] T021 [US1] Mount `OtpControl` next to the phone field in
  `web/src/pages/marketer/subscriber/PhoneSection.tsx`, and pass the draft, the `otp` status and
  the flush function from `SubscriberForm.tsx`. Update the header comment.

**Checkpoint**: T013 and T014 pass. The owner can verify their own phone on `https://localhost`
with the dev key (quickstart › manual steps 2–5).

---

## Phase 4: User Story 2 - Change after verification cancels it (Priority: P1)

**Goal**: A change to the phone, tower, category or prices clears the verification, and the
page shows «يحتاج تحقق جديد».

**Independent Test**: Verify, PATCH the category, and see `needs_reverify` with both draft columns
null.

### Tests for User Story 2

- [x] T022 [P] [US2] Write the context-change tests in `api/tests/integration/test_otp.py`
  (owner's test "cancellation on context change", research R5):
  - **Each field cancels**: after verification, each of these alone gives `needs_reverify` and
    clears `drafts.otp_verified_at` and `drafts.otp_context_hash`:
    - a different normalized phone;
    - the tower (also through an area change);
    - the category;
    - the admin changing the plan's trial price, then a draft save;
    - the admin changing the second price, then a draft save.
  - **Same normalized phone**: changing only spaces or digit script does not cancel.
  - **Revert stays cancelled**: putting the old category back keeps `needs_reverify`.
  - **Pending code**: changing the phone while a code is pending gives `otp_no_active` on verify.
    The status leaves `sent`.
- [x] T023 [P] [US2] Add Vitest cases in `web/src/__tests__/otpControl.test.tsx`: the
  `needs_reverify` status shows «يحتاج تحقق جديد» and enables «تحقّق». A pending code box closes when
  the status becomes `none`.

### Implementation for User Story 2

- [x] T024 [US2] In `draft_service.patch` (`api/app/services/draft_service.py`), after
  `refresh_copies`, clear `otp_verified_at` and `otp_context_hash` when the context changed. Use
  `otp_service.context_hash`. Do the same in any other save path that changes these fields (PUT).
- [x] T025 [US2] Make `otp_service.status` compare a `sent` challenge's `context_hash` with the
  draft's current values. If they differ, the code is treated as cancelled, and `verify` returns
  `otp_no_active` (data-model.md › Derived state).
- [x] T026 [US2] Write the Playwright scenario in `e2e/tests/otp.spec.ts`. With the fake sender and
  `OTP_FAKE_CODE`:
  - fill the subscription and the phone, tap «تحقّق», type 246810, and see «تم التحقق»;
  - change the category and see «يحتاج تحقق جديد»;
  - verify again and see ✓.

  Run it on desktop and on the phone projects.
- [x] T027 [US2] Show «يحتاج تحقق جديد» in `OtpControl.tsx`, and make `MissingSummary.tsx` treat unverified as missing
  «التحقق من الهاتف» (text only; the submit button stays disabled until 008).

**Checkpoint (end of batch 2)**: the acceptance criterion holds: a real code reaches the test
phone, verification succeeds, and changing the category cancels it.

---

## Phase 5: User Story 3 - Resend, wrong attempts, expiry and hourly limit (Priority: P2)

> **Note (batch 2)**: the limit and attempt code of T029/T030 already went in with T015, so a
> real send on `https://localhost` could not bypass them. Batch 3 adds their tests (T028) and the
> UI messages (T031).

**Goal**: The §8.3 limits, enforced on the server, with clear messages.

**Independent Test**: The owner's tests for expiry, 3 attempts and the hourly limit pass.

### Tests for User Story 3

- [ ] T028 [P] [US3] Write the limit tests in `api/tests/integration/test_otp.py` (owner's list,
  quickstart table):
  - **Expiry**: the right code at the validity + 1 minute gives 410 `otp_expired`. With the
    setting changed to 10 after the send, the code keeps its original expiry.
  - **3 attempts**: wrong, wrong gives `otp_wrong` with `attempts_left` 2 then 1. The third gives
    410 `otp_cancelled`, and the right code afterwards gives `otp_no_active` or `otp_cancelled`.
    A 5-digit entry gives `otp_code_format` and does not use an attempt.
  - **Resend wait**: a second send within 60 s gives 429 `otp_resend_wait` with `retry_after_s`.
    At 60 s it works. The new code replaces the old one, which then fails.
  - **Hourly limit**:
    - 5 sends to one phone from two drafts (clock + 61 s each) succeed, and the 6th gives 429
      `otp_hourly_limit` with `retry_after_min`.
    - At 60 minutes after the first send, it works again.
    - A deleted draft's sends still count (`request_id` null).
  - **Concurrency**: two parallel sends for one draft produce one row and one outbox entry.

### Implementation for User Story 3

- [ ] T029 [US3] Add the 60 s per-draft wait and the 5-per-hour per-phone check to
  `otp_service.send` in `api/app/services/otp_service.py`. Both are computed from `otp_challenges`
  under the locks (research R7). Build the Arabic messages with minutes and seconds.
- [ ] T030 [US3] Add the attempt counting, the expiry check and the code-format refusal to
  `otp_service.verify`. The third wrong entry returns `otp_cancelled` (contracts/api.md).
- [ ] T031 [US3] Show the server messages in `OtpControl.tsx`: remaining attempts,
  cancelled/expired with «اطلب رمزاً جديداً», the hourly limit with minutes, and the countdown from
  the server's `retry_after_s`.

---

## Phase 6: User Story 4 - Provider failure is clear (Priority: P3)

**Goal**: A failed send is explained, is not counted, and does not start the wait.

**Independent Test**: The owner's "failed send not counted" test passes.

### Tests for User Story 4

- [ ] T032 [P] [US4] Write the failure tests in `api/tests/integration/test_otp.py`:
  - **Not counted**: with `FakeOtpSender.fail_with` set to each reason, there is no row and the
    contracts/api.md code is returned. A send right after a failure works with no 60 s wait.
    5 failures plus 5 successes within one hour all go through.
  - **Busy**: `busy` returns `otp_provider_busy` with the minutes.
  - **No key**: `OTP_MODE=otpiq` with an empty key gives 503 `otp_not_configured`, and the draft
    still saves.

### Implementation for User Story 4

- [ ] T033 [US4] Finish the `OtpSendError` → `AppError` mapping in `otp_service.send`. Log the
  reason with the masked phone, and roll back without inserting.
- [ ] T034 [US4] Show the failure messages in `OtpControl.tsx`, and keep the button usable after a
  failure.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T035 Extend `api/tests/integration/test_log_safety.py`:
  - Send and verify, wrong and right.
  - Assert that the code, the full phone and the `OTPIQ_API_KEY` test value appear in no captured
    log line and in no response body.
  - Assert that `otp_challenges` stores no 6-digit plain code (SC-004).
- [ ] T036 [P] Add the OTP keys to the redaction check, if `logging_config.redact` misses
  `verificationCode` or `Bearer sk_`. Change only what the T035 test shows is missing, in
  `api/app/logging_config.py`.
- [x] T037 [P] Write `specs/007-phone-otp/manual-test-ar.md`, the Arabic manual test steps for
  `https://localhost` with the dev key: send, receive, verify, change the category, the leak
  check, the 25 IQD log line.
- [ ] T038 Run the whole api suite, `npm test` and the Playwright suite. Run `docker compose up` and
  do the manual steps once with the owner's dev key (one real send, 25 IQD).
- [ ] T039 [P] Add a one-line pointer to `specs/007-phone-otp/contracts/api.md` at the end of
  `specs/005-subscriber-form/contracts/api.md` (the draft output gains `otp`).
- [ ] T040 Tick the done tasks in this file, and run `/speckit-analyze` once more before merging.

---

## Dependencies & Execution Order

- **Setup (T001–T003)** → **Foundational (T004–T012)** → the stories.
- **US1 (T013–T021)** comes first. **US2** needs US1's service and status (T015, T016).
- **US3** and **US4** extend `otp_service.send` and `verify`, so they come after US1. They can run
  in either order, but both edit `otp_service.py`, so not in parallel.
- **Polish** comes after all stories.

Within a phase: tests first (they must fail), then models, then the service, then routes, then the
web.

### Parallel opportunities

- T002 and T003.
- T004 and T005 (tests).
- T009, T010, T011 and T012 (separate files).
- T013 and T014.
- T019 next to T015–T017.
- T022 and T023.

## Parallel Example: Foundational

```text
Task: "Rule tests in api/tests/unit/test_otp_rules.py" (T004)
Task: "Adapter tests in api/tests/integration/test_otpiq_sender.py" (T005)
Task: "OtpChallenge model in api/app/models/otp.py" (T009)
Task: "Error codes in api/app/errors.py" (T011)
```

## Implementation Strategy

### MVP (the acceptance criterion)

US1 + US2 (batch 2): a real code to the test phone, a successful verification, and a category
change that cancels it.

### Incremental delivery

1. **Batch 1**: config, rules, adapter, migration (no UI change).
2. **Batch 2**: the working flow on `https://localhost`.
3. **Batch 3**: limits, failures, log safety, manual test notes.
