# Implementation Plan: Rewards and Commissions

**Branch**: `017-commissions` | **Date**: 2026-11-26 | **Spec**: [spec.md](./spec.md)

**Input**:
- the feature spec `specs/017-commissions/spec.md`;
- the owner's answers of 2026-11-26: a request paid in a locked month does not count again after an undo and a
  re-link (Q1: A); amounts come from the tiers only (Q2: A); the marketer sees past months with «تم الدفع» or
  «غير مدفوع» (Q3: B); the spec assumptions approved;
- `docs/system.md` v1.23 §4.2, §6.4, §6.5, §7.2, §7.4, §9, §10 items 1, 5, 6, 11, 13, §12, §13;
- the constitution v1.4.0 (no change).

## Summary

The marketer sees their tier, expected amount and past months; the admin with `commissions` gets the monthly
report, marks finished months paid and locks them, and sees an alert when a paid link is undone.

| Part | What |
|---|---|
| Tier rule | pure `core/commission.py`: tier, amount, next tier (R1) |
| Count rule | one query: linked, not deleted, in the Baghdad month, split into counted / «بلا عمولة» / already paid (R2) |
| Payment | append-only `commission_payments` + `commission_payment_requests` (one payment per request) (R3, R4) |
| «تم الدفع» | finished month only, confirmed figures, row locks shared with the undo, audit `commission.paid` (R5, R10) |
| Alert | computed from `request_links` undos after `paid_at`; admin home warning for undos of the last 30 days, main admin and `commissions` only (R6) |
| Marketer | dashboard tier block; new «الأشهر السابقة» page (R11) |
| Admin pages | new «العمولات» page; two columns on «المسوّقون» (R8) |

Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web). No change.

**Primary Dependencies**: none new.

**Storage**: PostgreSQL 16, migration `0020_commissions`: two new tables, no change to existing ones. See
[data-model.md](./data-model.md).

**Testing**: pytest unit and integration, Vitest (run from PowerShell), Playwright
([R12](./research.md#r12-tests-principle-viii)). Each new test is run red before its code.

**Target Platform**: the company Linux server; admin panel in the browser; marketer app on phones (PWA).

**Project Type**: web app (`api/`, `web/`). No new service.

**Performance Goals**:
- marketer home and past months < 200 ms;
- a month report for ~50 marketers and a few thousand links < 1 s (existing partial index on linked rows).

**Constraints**:
- One count rule for home, past months, report and marketers page.
- A paid month never changes; a request is paid at most once (database key).
- A refused pay writes nothing; the undo path of 013 is not changed.
- No phone, username, identity number or image in commission screens; the marketer never sees who paid.
- Baghdad month boundaries, UTC storage.

**Scale/Scope**:
- 1 migration; 1 pure module (`core/commission.py`); 2 models (`CommissionPayment`,
  `CommissionPaymentRequest`); 1 service (`commission_service`); 1 router (`api/admin_commissions.py`);
- changed: `core/access.py` (page `commissions`), `services/link_service.py` (`marketer_counts` via the shared
  rule), `schemas/dashboard.py`, `api/marketer.py` (past months), `api/marketers.py` (month summary),
  `api/admin.py` + `schemas/admin_requests.py` (`commission_alerts`), `errors.py` (4 codes), `main.py`;
- web: new `lib/commissions.ts`, `pages/admin/commissions/{Commissions,CommissionDetail,PayDialog}.tsx`,
  `pages/marketer/PastMonths.tsx`; changed `auth/access.ts`, `layouts/AdminLayout.tsx`, `router.tsx`,
  `pages/marketer/Dashboard.tsx`, `pages/admin/Marketers.tsx`, `pages/admin/Home.tsx`, `lib/labels.ts`,
  `lib/auditFormat.ts`; shared fixture `page_access.json` (api and web copies).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | No change to checks, decisions or transitions. Only `linked` requests count; legacy and SAS rows have no marketer and cannot enter the query. |
| II. Protection of Identity Documents | ✅ | Allow-list schemas without phone, username, identity numbers, card fields or images; the audit entry carries figures only; logs carry marketer id and month. |
| III. Permanent Audit Trail | ✅ | `commission.paid` with who, when and the locked figures; tier changes already audited (004). Payments are never edited or deleted; the undo history stays in `request_links`. |
| IV. Recorded Values Are Immutable | ✅ | The paid month stores count, tier, rate, amount and its requests; later tiers or undos never change them (tested). |
| V. Mobile-First and Arabic | ✅ | Arabic texts and RTL; the marketer views are phone-first; amounts formatted with the existing `money.ts`. |
| VI. Simplicity | ✅ | No manual adjustments (Q2), no stored counters, alerts computed from existing history; rules in `docs/system.md` 1.23 first. |
| VII. Fixed Technology Stack | ✅ | No new technology or service. |
| VIII. Tested Business Rules | ✅ | Tier boundaries from a fixture; counts across statuses, types, deletion, imports, months, undo and re-link; payment lock, concurrency and permissions (R12). |
| IX. Server-Side Authorization | ✅ | `require_permission("commissions")` / `("marketers")`; marketer routes filtered by the caller; the home alert field only for main admin and `commissions`. |
| X. Time Handling | ✅ | Months from `baghdad_month_bounds`; `paid_at` from `utc_now()`; boundary tests with the test clock. |

Gate result: **pass**. Re-checked after Phase 1: **pass**.

## Project Structure

### Documentation (this feature)

```text
specs/017-commissions/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/api.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
api/
├── migrations/versions/0020_commissions.py
├── app/
│   ├── errors.py                          # month_not_finished, nothing_to_pay, commission_changed, already_paid
│   ├── core/access.py                     # page "commissions"
│   ├── core/commission.py                 # new: tier_for, amount, next_tier, month keys (R1)
│   ├── models/commission.py               # new: CommissionPayment, CommissionPaymentRequest
│   ├── schemas/commissions.py             # new: report, row, detail, pay body, past months
│   ├── schemas/dashboard.py               # tier_rate, expected_amount, next_tier
│   ├── schemas/admin_requests.py          # HomeOut.commission_alerts
│   ├── services/commission_service.py     # new: month_split, report, detail, pay, alerts, past months
│   ├── services/link_service.py           # marketer_counts uses commission_service
│   ├── api/admin_commissions.py           # new router
│   ├── api/marketer.py                    # /commissions/months
│   ├── api/marketers.py                   # /month-summary
│   ├── api/admin.py                       # commission_alerts by role/permission
│   └── main.py                            # include router
└── tests/
    ├── fixtures/{commission_tier_cases.json,page_access.json}
    ├── unit/test_commission.py
    └── integration/{test_commission_counts,test_commission_pay,test_commission_alerts,
                     test_commission_access,test_commission_consistency,test_migration_0020}.py

web/src/
├── lib/commissions.ts
├── auth/access.ts                         # page commissions
├── layouts/AdminLayout.tsx                # menu «العمولات»
├── router.tsx                             # /admin/commissions, /commissions
├── pages/admin/commissions/{Commissions,CommissionDetail,PayDialog}.tsx
├── pages/admin/{Home,Marketers}.tsx
├── pages/marketer/{Dashboard,PastMonths}.tsx
├── lib/{labels,auditFormat}.ts
└── __tests__/{commissions,payDialog,pastMonths,dashboard,marketers,adminHome}.test.tsx

e2e/tests/commissions.spec.ts
```

**Structure Decision**: the existing `api/` + `web/` layout. Commissions get their own service and router
(permission `commissions`, own page); the marketer home keeps its endpoint and reads its counts from the same
service so every screen shares one rule.

## Complexity Tracking

No violations.

## Owner decision at plan review

The admin home warning «يوجد تراجع بعد الدفع» covers undos after payment in the last 30 days; the report keeps
every alert for good (owner, 2026-11-26; `docs/system.md` 1.23 §9; R6).
