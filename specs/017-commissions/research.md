# Research: 017 Rewards and Commissions

All spec questions were answered by the owner on 2026-11-26 (Q1: A, Q2: A, Q3: B, assumptions approved). No
open unknowns remain; the decisions below fix how the rules map onto the existing code.

## R1. One pure module for the tier rule

- **Decision**: `api/app/core/commission.py` holds pure functions: `tier_for(count, tiers) -> (min_count, rate)`
  (the tier with the highest `min_count` ≤ count), `amount(count, tiers) = rate × count`, `next_tier(count,
  tiers) -> (remaining, rate) | None` (None in the top tier), and `month_key` parse/format (`YYYY-MM`). The web
  formats only; it never computes a tier.
- **Rationale**: Principle VIII names commission tiers; a pure module is tested with a shared fixture of boundary
  cases (0, 29, 30, 49, 50, one tier only, 20 tiers). One rule serves the home, past months, the report and the
  marketers page (FR-020, SC-002).
- **Alternatives**: computing in SQL (harder to test at the boundaries); computing in the web (Principle IX).

## R2. The count rule as one query builder

- **Decision**: `commission_service.month_split(db, start, end, marketer_ids=None)` returns per marketer three
  numbers for a Baghdad month: `counted`, `without_commission`, `paid_before`. Base set: `status = 'linked'`,
  `deleted_at IS NULL`, `linked_at ∈ [start, end)`. A row is:
  - `paid_before` when an entry for the request exists in `commission_payment_requests` (Q1: a paid request
    never counts again);
  - else `without_commission` when `counts_commission` is false;
  - else `counted`.
  The marketer home shows `without_commission + paid_before` as «بلا عمولة» (FR-003, FR-016); the report
  details list the two separately.
- **Rationale**: 013's `marketer_counts` already filters linked, not deleted, in the month; this extends it with
  one `NOT EXISTS`. Legacy and SAS subscribers live in their own tables with no `marketer_id`, so they can never
  enter this query (FR-002); a test proves that importing them changes no count.
- **Note**: a paid month's own requests are in `commission_payment_requests` too, so the live rule would show them
  as `paid_before` — that is why a paid month is never computed live (R4).
- **Alternatives**: a stored running counter per month (drifts on undo); a `paid_in` column on `requests`
  (mixes a commission fact into the request row and its checks).

## R3. Payment storage, append-only

- **Decision**: table `commission_payments` (one row per marketer and month, unique) with `count`,
  `tier_min_count`, `rate`, `amount`, `paid_by`, `paid_at`; table `commission_payment_requests` (`payment_id`,
  `request_id` primary key) — the request id is the key, so a request is in at most one payment, enforced by the
  database. The code has no update or delete path; checks: `count > 0`, `amount = count × rate`, `month` is the
  first day of a month.
- **Rationale**: Principle IV (a paid month is locked) and FR-012/FR-013; the request list makes Q1 a single
  lookup and lets the report show what was paid.
- **Alternatives**: JSON list of request ids on the payment (no database guarantee of one payment per request).

## R4. Paid month versus unpaid month

- **Decision**: for each (marketer, month) the service first looks for a payment. Paid → the stored count, tier,
  rate and amount, the stored request list, plus «today's count» = stored requests that are still linked with
  `linked_at` in that month. Unpaid → R2 and R1 with today's tiers (FR-005). The current month is never paid.
- **Rationale**: a paid month can only go down (linking happens now), so comparing stored with today's count is
  the whole alert.

## R5. «تم الدفع» under locks, with the confirmed figures

- **Decision**: `POST …/pay` body `{count, amount}` = what the dialog showed. In one transaction: refuse a month
  that is not finished (`month_not_finished`), lock the marketer's counted requests of that month `FOR UPDATE`
  (the same row lock `link_service.unlink` takes), recompute, refuse when the figures differ from the body
  (`commission_changed`, «تغيّرت الأرقام، راجعها من جديد») or the count is 0 (`nothing_to_pay`), insert the
  payment and its requests, write the audit entry, commit. A second payment hits the unique key and answers
  `409 already_paid` «تم تسجيل الدفع لهذا الشهر مسبقاً» with nothing written.
- **Rationale**: an undo running at the same moment either finishes before (the count is lower and the admin is
  told) or waits and then sees a paid request (an alert, R6). The admin never locks figures they did not see.
- **Alternatives**: an advisory lock per marketer (the row locks already serialize with the undo).

## R6. The alert «تراجع بعد الدفع» and the home warning

- **Decision**: computed on read, nothing new is written by the undo: alert lines = `request_links` rows of kind
  `unlinked` whose request is in a payment and whose time is after `paid_at`, with request number, time and
  reason code. The report row shows the lines and «المدفوع N، اليوم M» for good. The admin home
  (`GET /api/admin/home`) gains `commission_alerts: int` = the number of alert lines whose undo time is within the
  last 30 days (`at > now − 30 days`), for the main admin and `commissions` holders only; null for other admins
  (owner, 2026-11-26).
- **Rationale**: 013's undo stays untouched (no new write path, no new failure mode); the history is already
  append-only in `request_links`.
- **Window**: with no dismiss, an unbounded home warning would stay forever; the owner chose a 30-day window for
  the home only (a fixed rolling window, tested at 30 days ± 1 minute with the test clock).
- **Alternatives**: an alert table written by the undo (a second write in 013's transaction for the same fact).

## R7. Months to pick

- **Decision**: admin month list = every Baghdad month from the month of the earliest `linked_at` or payment to
  the current month, newest first (`GET /api/admin/commissions/months`). Marketer past months = finished months in
  which the marketer has a linked request or a payment, newest first.
- **Rationale**: FR-008 and FR-007; an empty month in between is harmless in the picker.

## R8. API shape and permissions

- **Decision**: new router `api/admin_commissions.py` with `require_permission("commissions")`; marketer routes in
  `api/marketer.py` with `require_roles("marketer")` reading only `marketer_id = caller`; the marketers page gets
  `GET /api/admin/marketers/month-summary` under `require_permission("marketers")` (count and expected amount
  only). New page key `commissions` in both access maps and the shared `page_access.json`.
- **Rationale**: Principle IX; the existing permission `commissions` (002) finally gets its page.

## R9. What the report and details may show

- **Decision**: allow-list schemas: rows carry marketer id and name, figures, payment who/when, alert lines;
  details carry request number, full name, type, tower name and code, link time. No phone, username, national
  ID, family number, card field or image (FR-010, Principle II). The marketer's past months carry figures and
  «تم الدفع»/«غير مدفوع» only — never `paid_by`, `paid_at` or alerts (FR-007).

## R10. Audit

- **Decision**: `commission.paid`, entity type `commission_payment`, entity id `"<marketer_id>:<YYYY-MM>"`,
  `after = {marketer_id, month, count, tier_min_count, rate, amount}`, no request numbers or names. Tier changes
  keep 004's `reward_tiers.updated` with old and new tiers (FR-017). Refused actions write nothing (FR-018).
  Web: label «تسجيل دفع عمولة» in `labels.ts` and its formatter in `auditFormat.ts`.

## R11. The marketer home

- **Decision**: `MarketerDashboard` gains `tier_rate`, `expected_amount`, `next_tier: {remaining, rate} | null`;
  `linked_without_commission` now also includes `paid_before`. `link_service.marketer_counts` delegates the counts
  to `commission_service` so the home and the report share one rule. A link «الأشهر السابقة» opens a new marketer
  page `/commissions`.

## R12. Tests (Principle VIII)

- Unit: `test_commission.py` against `fixtures/commission_tier_cases.json` (also read by a Vitest test of the
  money formatting only).
- Integration: `test_commission_counts` (statuses, types, «لا» returns, deleted, legacy and SAS imports change
  nothing, month boundaries at Baghdad midnight with the test clock, undo and re-link across months, Q1
  re-link after payment), `test_commission_pay` (finished month only, zero, figures changed, double pay and two
  concurrent pays, tiers change after pay, audit), `test_commission_alerts` (undo after pay, home field by role),
  `test_commission_access` (every route by role and permission, marketer sees only own months and no payer),
  `test_commission_consistency` (home = past months = report = marketers page), `test_migration_0020`.
- Web: Vitest for the home tier block, past months, report, pay dialog, alert, marketers columns.
- e2e: `e2e/tests/commissions.spec.ts`: link, report, pay, undo after pay, alert, marketer past months.
- Each new test is run red before its code.
