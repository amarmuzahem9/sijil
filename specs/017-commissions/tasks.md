---

description: "Task list for feature 017: Rewards and Commissions"
---

# Tasks: Rewards and Commissions

**Input**: Design documents from `specs/017-commissions/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required by constitution Principle VIII and by the owner's rule: **each new test is run red before its
code is written**. Report red and green for every test task.

**Test rules**:
- Synthetic data only: made-up names, numbers and phones; no real card images or subscribers (CLAUDE.md).
- Every run is on the owner's machine only (local Docker); nothing runs on staging or production.
- Requests from `api/tests/helpers/requests.py::request_factory` (`status="linked"`, `link_request`,
  `mark_deleted`); admins from `api/tests/helpers/review.py::admin_with`; time from the `frozen_clock` fixture of
  `api/tests/conftest.py`; legacy and SAS rows from `api/tests/helpers/legacy.py` and `api/tests/helpers/sas.py`.
- Vitest runs from PowerShell (project note).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md
- **Paths**: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

**Implementation batches** (each ends at a phase boundary and with a commit):

| Batch | Phases | Tasks |
|---|---|---|
| 1 | 1–2 (Setup, Foundational) | T001–T013 |
| 2 | 3 (US1 marketer home and past months) | T014–T023 |
| 3 | 4 (US2 commission report) | T024–T033 |
| 4 | 5 (US3 «تم الدفع» and the lock) | T034–T041 |
| 5 | 6–7 (US4 alert after payment, US5 marketers page) | T042–T051 |
| 6 | 8 (Polish, e2e, manual test) | T052–T058 |

---

## Phase 1: Setup

- [x] T001 Confirm the baseline: `docker compose up -d`, then `docker compose exec api pytest` and the web suite
  (`npm test` in `web/`, from PowerShell) are green on the branch before any change; note the counts in the batch
  report.
- [x] T002 [P] Add error codes with their Arabic messages in `api/app/errors.py` (contracts/api.md › pay):
  `month_not_finished` (409, «لا يُسجَّل الدفع قبل نهاية الشهر»), `nothing_to_pay` (409, «لا يوجد عدد محسوب
  لهذا الشهر»), `commission_changed` (409, «تغيّرت الأرقام، راجعها من جديد»), `already_paid` (409, «تم تسجيل الدفع
  لهذا الشهر مسبقاً»).

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the tier rule, the payment tables, the shared count rule and the page key every story uses.

### Tests (write first, run red)

- [x] T003 [P] Create the fixture `api/tests/fixtures/commission_tier_cases.json` (tiers + count → tier min,
  rate, amount, next tier or null): default tiers at 0, 29, 30, 49, 50, 120; a single tier at 0; 20 tiers; a
  count of 0 with a second tier at 1. Unit test `api/tests/unit/test_commission.py` drives `tier_for`, `amount`,
  `next_tier` from it, and `month_key` parse/format (`2026-10` ↔ first day; `2026-13`, `26-10`, `2026-1` refused)
  (research R1).
- [x] T004 [P] Migration test `api/tests/integration/test_migration_0020.py`: after upgrade the tables of
  data-model.md exist; `UNIQUE (marketer_id, month)` refuses a second data-model.md
  `commission_payments.marketer_id` + `commission_payments.month`; checks refuse data-model.md
  `commission_payments.month` not on day 1, `commission_payments.count` ≤ 0, `commission_payments.tier_min_count`
  above count, `commission_payments.rate` out of range, `commission_payments.amount` ≠ count × rate; data-model.md
  `commission_payment_requests.request_id` as primary key refuses the same request in a second payment;
  `commission_payment_requests.payment_id` required; downgrade to 0019 removes both tables.
- [x] T005 [P] Integration test `api/tests/integration/test_commission_counts.py` for
  `commission_service.month_split` (research R2): only `linked` counts (draft, pending, rejected, approved not
  linked give 0); new, additional and return «نعم» → counted; return «لا» → without_commission; a deleted pending
  or rejected request never appears, and the database refuses a deleted linked row (check of 011); importing legacy and SAS rows with
  the same phone/family as linked requests changes no number; links at 23:59:59 on the last day and 00:00:00 on
  the 1st (Baghdad) fall in the right months; undo removes from its month; re-link counts in the new month once;
  a request in `commission_payment_requests` lands in paid_before, not counted (Q1); an archived marketer still
  counts.
- [x] T006 [P] Add `commissions` to the shared page fixtures `api/tests/fixtures/page_access.json` and
  `web/src/__tests__/fixtures/page_access.json` (main admin yes, `commissions` holder yes, any other admin no,
  marketer no); the existing access tests on both sides go red.

### Implementation

- [x] T007 Create `api/app/core/commission.py` (`tier_for`, `amount`, `next_tier`, `month_key`, `parse_month`);
  T003 green.
- [x] T008 Write migration `api/migrations/versions/0020_commissions.py` (revises `0019`): table
  `commission_payments` with data-model.md `commission_payments.id`, `commission_payments.marketer_id`,
  `commission_payments.month`, `commission_payments.count`, `commission_payments.tier_min_count`,
  `commission_payments.rate`, `commission_payments.amount`, `commission_payments.paid_by`,
  `commission_payments.paid_at`, the unique key and the month index; table `commission_payment_requests` with
  data-model.md `commission_payment_requests.request_id`, `commission_payment_requests.payment_id` and its index;
  T004 green.
- [x] T009 [P] Mirror the migration in `api/app/models/commission.py` (`CommissionPayment`,
  `CommissionPaymentRequest`), registered in `api/app/models/__init__.py`.
- [x] T010 Create `api/app/services/commission_service.py` with `month_split(db, month, marketer_ids=None)`
  returning per marketer counted / without_commission / paid_before (research R2), using
  `baghdad_month_bounds` for the month; T005 green.
- [x] T011 [P] Add helper `pay_month(db, marketer, month, admin, requests, rate=5000, tier_min_count=0,
  at=None)` to `api/tests/helpers/requests.py` that inserts a payment of exactly `requests` (for tests that need
  a paid month without going through the service).
- [x] T012 [P] Add page `"commissions": ("commissions",)` to `api/app/core/access.py` and `commissions:
  ['commissions']` with path `/admin/commissions` to `web/src/auth/access.ts`; T006 green on both sides.
- [x] T013 [P] Add audit label `'commission.paid': 'تسجيل دفع عمولة'` in `web/src/lib/labels.ts` and its
  formatter (marketer, month, count, rate, amount) in `web/src/lib/auditFormat.ts`, with a Vitest case in the
  existing audit format test (research R10).

**Checkpoint**: batch 1 commit.

---

## Phase 3: User Story 1 — The marketer sees their tier and expected amount (Priority: P1) 🎯 MVP

**Goal**: the home shows tier, expected amount and «باقيلك»; «الأشهر السابقة» lists finished months.

**Independent Test**: spec US1 (27 links → 5,000, 135,000, «باقيلك 3 وتصير 7,000 للمشترك»; 3 more → 7,000,
210,000, «باقيلك 20…»; past months with «تم الدفع» / «غير مدفوع»).

### Tests (write first, run red)

- [x] T014 [P] [US1] New `api/tests/integration/test_commission_dashboard.py`: `GET /api/marketer/dashboard` returns `tier_rate`,
  `expected_amount`, `next_tier` for 0, 27, 30, 50 counted links; `next_tier` null in the top tier; a «لا» return
  and a paid-before request add to `linked_without_commission` only; a tier change is reflected on the next call
  (contracts/api.md › dashboard).
- [x] T015 [P] [US1] Integration test `api/tests/integration/test_marketer_past_months.py`: `GET
  /api/marketer/commissions/months` lists finished months with a link or a payment, newest first, never the
  current month; a paid month shows the stored figures after a tier change and `paid: true`; an unpaid month
  follows today's tiers; the body has no `paid_by`, `paid_at` or alerts; marketer B never sees A's months; an
  admin gets 403 (FR-007, research R9).
- [x] T016 [P] [US1] Vitest `web/src/__tests__/dashboard.test.tsx`: the tier block shows rate, amount and
  «عندك N، باقيلك K وتصير R للمشترك»; no «باقيلك» when `next_tier` is null; a link «الأشهر السابقة».
- [x] T017 [P] [US1] Vitest `web/src/__tests__/pastMonths.test.tsx`: lines with month, count, «بلا عمولة», rate,
  amount and «تم الدفع» / «غير مدفوع»; empty state «لا توجد أشهر سابقة».

### Implementation

- [x] T018 [US1] In `api/app/services/commission_service.py` add `marketer_current(db, user)` (counted,
  without_commission + paid_before, tier, amount, next tier) and `marketer_past_months(db, user)` (research R4,
  R7, R11).
- [x] T019 [US1] Extend `api/app/schemas/dashboard.py` (`tier_rate`, `expected_amount`, `NextTier | None`) and
  make `link_service.marketer_counts` in `api/app/services/link_service.py` take its numbers from
  `commission_service.marketer_current`; the 013 counter tests stay green; T014 green.
- [x] T020 [US1] Add schemas `PastMonth`, `PastMonths` in new `api/app/schemas/commissions.py` and route `GET
  /commissions/months` in `api/app/api/marketer.py` (`require_roles("marketer")`); T015 green.
- [x] T021 [P] [US1] Create `web/src/lib/commissions.ts` (types and the marketer calls) using `lib/money.ts` for
  amounts.
- [x] T022 [US1] Tier block and «الأشهر السابقة» link in `web/src/pages/marketer/Dashboard.tsx`; T016 green.
- [x] T023 [US1] New page `web/src/pages/marketer/PastMonths.tsx`, route `/commissions` in `web/src/router.tsx`
  under the marketer layout; T017 green.

**Checkpoint**: batch 2 commit.

---

## Phase 4: User Story 2 — The admin reviews the monthly commission report (Priority: P1)

**Goal**: «العمولات» with month picker, rows, total and details, for main admin and `commissions` only.

**Independent Test**: spec US2.

### Tests (write first, run red)

- [x] T024 [P] [US2] Integration test `api/tests/integration/test_commission_report.py`: `GET
  /api/admin/commissions/months` (from the earliest link or payment to the current month, newest first);
  `GET /api/admin/commissions?month=` rows only for marketers with a linked request or a payment in the month,
  ordered by name, with count, without_commission, paid_before, tier, amount, `payable`, `payment: null`, and
  `total_amount`; archived and stopped marketers included; a malformed or future month → 422 (contracts/api.md).
- [x] T025 [P] [US2] Integration test in the same file for `GET /api/admin/commissions/{month}/marketers/{id}`:
  `counted`, `without_commission`, `paid_before` (with `paid_month`) lists; 404 when the marketer has no row; the
  response keys are exactly the allow-list (no phone, username, national ID, family number, card or image key)
  (FR-010, research R9).
- [x] T026 [P] [US2] Integration test `api/tests/integration/test_commission_access.py`: every
  `/api/admin/commissions*` route → 403 for a marketer and for admins with each other permission; 200 for main
  admin and a `commissions`-only admin; a request without a session → 401; no route edits or removes a payment
  (DELETE/PATCH on the pay path → 405) (FR-013).
- [x] T027 [P] [US2] Vitest `web/src/__tests__/commissions.test.tsx`: month picker defaults to current; rows,
  states «غير مدفوع» / «تم الدفع»; total; opening a row shows the three lists; menu entry «العمولات» only when
  `canAccess(commissions)`.

### Implementation

- [x] T028 [US2] In `api/app/services/commission_service.py` add `months(db)`, `report(db, month)` (paid rows
  from the payment, unpaid from `month_split` + today's tiers, research R4) and `detail(db, month, marketer_id)`.
- [x] T029 [US2] Report, row and detail schemas (allow-list) in `api/app/schemas/commissions.py`.
- [x] T030 [US2] New router `api/app/api/admin_commissions.py` (`require_permission("commissions")`) with the
  three GET routes, included in `api/app/main.py`; T024–T026 green.
- [x] T031 [P] [US2] Admin calls and types in `web/src/lib/commissions.ts`.
- [x] T032 [US2] Pages `web/src/pages/admin/commissions/Commissions.tsx` and `CommissionDetail.tsx`; route in
  `web/src/router.tsx` with `page('commissions', …)`; menu entry «العمولات» in `web/src/layouts/AdminLayout.tsx`;
  T027 green.
- [x] T033 [US2] Consistency check in `api/tests/integration/test_commission_report.py`: for the same marketer
  and month, the report row equals the marketer's dashboard (current month) and past months line (finished
  month) (SC-002).

**Checkpoint**: batch 3 commit.

---

## Phase 5: User Story 3 — The admin marks a month paid and it is locked (Priority: P1)

**Goal**: «تم الدفع» on finished months with the confirmed figures; the paid month never changes.

**Independent Test**: spec US3.

### Tests (write first, run red)

- [ ] T034 [P] [US3] Integration test `api/tests/integration/test_commission_pay.py` (contracts/api.md › pay):
  success stores data-model.md `commission_payments.count`, `commission_payments.tier_min_count`,
  `commission_payments.rate`, `commission_payments.amount`, `commission_payments.paid_by`,
  `commission_payments.paid_at` and one `commission_payment_requests` row per counted request, and one audit
  entry `commission.paid` with figures and no request numbers or names; refusals write nothing (no payment, no
  audit): current month → `month_not_finished`, count 0 → `nothing_to_pay`, body figures differ →
  `commission_changed`, second pay → `already_paid`, unknown marketer → 404, no permission → 403; after a tier
  change the paid row keeps its rate and amount while an unpaid month moves (FR-005).
- [ ] T035 [P] [US3] Concurrency test in the same file: two pays on the same row in two sessions → one 200, one
  `already_paid`; a pay and an undo of one of its requests in two sessions → either the pay sees the lower count
  (`commission_changed`) or the undo runs after it (paid row unchanged) — never a payment that includes an undone
  request (research R5).
- [ ] T036 [P] [US3] Vitest `web/src/__tests__/payDialog.test.tsx`: the dialog shows count, rate and amount and
  sends them; the button is hidden when `payable` is false; Arabic messages for the four 409 codes; the row
  turns «تم الدفع» with who and when after success.

### Implementation

- [ ] T037 [US3] `pay(db, admin, month, marketer_id, count, amount)` in `api/app/services/commission_service.py`:
  finished-month check, `FOR UPDATE` on the counted requests, recompute, compare, insert payment and requests,
  audit, commit; unique-key violation → `already_paid` (research R5, R10); T034, T035 green.
- [ ] T038 [US3] Pay body schema in `api/app/schemas/commissions.py` and route `POST
  /{month}/marketers/{marketer_id}/pay` in `api/app/api/admin_commissions.py`.
- [ ] T039 [P] [US3] `pay` call in `web/src/lib/commissions.ts`.
- [ ] T040 [US3] New `web/src/pages/admin/commissions/PayDialog.tsx` and the «تم الدفع» button on the row in
  `Commissions.tsx`; T036 green.
- [ ] T041 [US3] Add a test in `api/tests/integration/test_commission_pay.py` that a payment made by
  `commission_service.pay` and one made by the helper `pay_month` (T011) for the same requests give the same rows,
  so the helper stays faithful to the service; the suite stays green.

**Checkpoint**: batch 4 commit.

---

## Phase 6: User Story 4 — An undo after payment shows as an alert (Priority: P2)

**Goal**: paid figures never move; the report shows «تراجع بعد الدفع»; the admin home warns for 30 days.

**Independent Test**: spec US4.

### Tests (write first, run red)

- [ ] T042 [P] [US4] Integration test `api/tests/integration/test_commission_alerts.py`: an undo of a paid
  request after `paid_at` keeps the paid figures and adds an alert line (number, time, reason) and `count_today`
  one lower; an undo before payment adds none; re-linking that request in a later month puts it in
  `paid_before`, not counted (FR-016); `GET /api/admin/home` `commission_alerts` = 1 for main admin and a
  `commissions` admin, `null` for a `link`-only admin; with `frozen_clock` 30 days − 1 minute after the undo it is
  1, 30 days + 1 minute after it is 0, while the report alert stays (research R6).
- [ ] T043 [P] [US4] Vitest `web/src/__tests__/commissions.test.tsx` (alert part): the paid row shows «تراجع بعد
  الدفع» lines and «المدفوع N، اليوم M»; Vitest `web/src/__tests__/adminHome.test.tsx`: warning «يوجد تراجع بعد
  الدفع» with a link to `/admin/commissions` when `commission_alerts > 0`, nothing when 0 or null.

### Implementation

- [ ] T044 [US4] Alerts and `count_today` in `report` of `api/app/services/commission_service.py`, plus
  `home_alert_count(db, now)` (30-day window); T042 report part green.
- [ ] T045 [US4] `commission_alerts` in `HomeOut` (`api/app/schemas/admin_requests.py`), filled in
  `api/app/api/admin.py` for main admin and `commissions` holders; T042 green.
- [ ] T046 [US4] Alert lines on the paid row in `web/src/pages/admin/commissions/Commissions.tsx` and the warning
  in `web/src/pages/admin/Home.tsx`; T043 green.

---

## Phase 7: User Story 5 — The marketers page shows the month count and commission (Priority: P3)

**Goal**: «المسوّقون» shows this month's count and expected amount, without payment.

**Independent Test**: spec US5.

### Tests (write first, run red)

- [ ] T047 [P] [US5] Integration test `api/tests/integration/test_marketers_month_summary.py`: `GET
  /api/admin/marketers/month-summary` (current month, count and amount per marketer, equal to each marketer's
  dashboard); 403 without `marketers`; no request data in the body.
- [ ] T048 [P] [US5] Vitest `web/src/__tests__/marketers.test.tsx`: columns «عدد الشهر» and «العمولة المتوقعة»;
  no «تم الدفع».

### Implementation

- [ ] T049 [US5] `month_summary(db)` in `api/app/services/commission_service.py` and the route in
  `api/app/api/marketers.py` (declared before `/{user_id}` routes); T047 green.
- [ ] T050 [P] [US5] Call in `web/src/lib/commissions.ts`.
- [ ] T051 [US5] Two columns in `web/src/pages/admin/Marketers.tsx`; T048 green.

**Checkpoint**: batch 5 commit.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T052 [P] e2e `e2e/tests/commissions.spec.ts` (local Docker only): link synthetic requests for a marketer,
  then an e2e-only helper in `e2e/tests/helpers.ts` moves those requests' `linked_at` (and their `request_links`
  times) one month back in the local e2e database through `docker compose exec db psql` (the e2e has no test
  clock); open «العمولات», check row and details, «تم الدفع», undo one link, see
  the alert and the home warning, the marketer's «الأشهر السابقة» shows «تم الدفع»; a `link`-only admin has no
  «العمولات» menu.
- [ ] T053 [P] Log check in `api/tests/integration/test_commission_pay.py`: the pay logs only marketer id, month
  and amount; no names, phones or request numbers (Principle II).
- [ ] T054 [P] Performance check in `api/tests/integration/test_commission_report.py`: a month with 50 marketers
  and 3,000 links builds the report in under 1 s on the local stack (plan › Performance Goals).
- [ ] T055 Run the whole suite: `docker compose exec api pytest`, the web suite from PowerShell, and the e2e
  suite; all green; note counts.
- [ ] T056 `docker compose up` on the owner's machine: the app starts and migration 0020 is applied.
- [ ] T057 Write `specs/017-commissions/manual-test-ar.md`: the Arabic manual steps for the owner, from
  quickstart.md, local machine only.
- [ ] T058 Mark the tasks done and check `docs/system.md` 1.23 matches what was built; batch 6 commit.

**Checkpoint**: batch 6 commit.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → stories. Phase 2 blocks every story (tables, rule, page key).
- US1 needs only Phase 2. US2 needs Phase 2 (paid rows come from `pay_month` until US3). US3 needs US2 (row and
  page). US4 needs US3 (a real payment) and US2 (row). US5 needs only Phase 2 and US1's `marketer_current`.
- Within a story: tests (red) → service → schema/route → web.

## Parallel Examples

- Phase 2 tests T003, T004, T005, T006 together; then T009, T011, T012, T013 beside T007/T008/T010.
- US1: T014–T017 together; T021 beside T018–T020.
- US2: T024–T027 together; T031 beside T028–T030.
- US3: T034–T036 together; T039 beside T037–T038.
- US4 and US5 tests (T042, T043, T047, T048) together.

## Implementation Strategy

- MVP = batches 1–2: the marketer sees the tier, the amount and past months.
- Batches 3–4 give the admin the report and the payment lock; batch 5 the alert and the marketers page; batch 6
  the e2e, the checks and the manual test.
- Each batch ends with green suites, a commit and Arabic manual steps for the owner. Everything runs on the
  owner's machine only.

## Notes

- 013's link and undo code is not changed; only `marketer_counts` reads its numbers from the new service.
- No manual adjustment exists (Q2); no task adds one.
