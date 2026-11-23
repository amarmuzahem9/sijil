# Implementation Plan: Admin Review of Pending Requests

**Branch**: `010-admin-request-review` | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**:
- the feature spec `specs/010-admin-request-review/spec.md`;
- the owner's answers of 2026-11-23:
  - Q1: a clash found by the re-check is a red warning, and accepting despite it needs a second
    confirmation and is audited;
  - Q2: a fixed list of rejection reasons plus «سبب آخر»;
  - Q3: the admin home counts are in 010;
- the analysis answer D1: a pin is audited by reference to its pin row (constitution v1.2.1);
- `docs/system.md` v1.14 §6.4, §7.2, §10;
- the constitution v1.2.1.

## Summary

008 and 009 leave requests in `pending_review` with their reasons and linked records. Nobody can see
them yet. 010 adds the review side:

| Part | What |
|---|---|
| «طلبات بالانتظار» | the list, oldest first, filtered by reason (R13) |
| Request file | every field, the images (with logged access), the linked records with their basis (R8, R9) |
| Decision | accept (with the commission answer for a return) or reject (fixed reason or «سبب آخر» with text). One decision per request, under a row lock (R1, R2, R6, R7) |
| Pinning numbers | from the reading, the MRZ, the marketer, or typed. A full re-check follows: reasons are marked, `new` may become `additional`, and clashes become warnings (R3, R4, R5) |
| Warnings | computed live. Accepting despite them needs the exact confirmed set and is audited (R7) |
| Admin home | today and month counts in Baghdad time (R10) |
| Marketer | sees «تمت الموافقة» or «تم رفض الطلب» with the reason. Nothing else (R11) |

Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web). No change.

**Primary Dependencies**: none new.

**Storage**: PostgreSQL 16, migration `0013_admin_review`:
- decision columns and the submitted values on `requests`;
- reason state on `request_reasons`;
- the new table `request_number_pins`;
- `image_access_log.request_id`.

See [data-model.md](./data-model.md).

**Testing**: pytest unit and integration tests, Vitest, Playwright ([R14](./research.md#r14-tests-principle-viii)).
Each new test is run red before its code.

**Target Platform**: the company Linux server. The admin pages are used on desktop and phone.

**Project Type**: web app (`api/`, `web/`). No new service.

**Performance Goals**:
- the pending list and the request file load in under 1 s with a few hundred pending requests;
- accept, reject and pin finish in under 2 s (SC-001: a decision in under 2 minutes).

**Constraints**:
- No linked-record data or warnings in any marketer response.
- No identity numbers, phone or names in audit or log lines.
- One decision per request under concurrency.
- Pin re-checks hold the same advisory locks as submission.

**Scale/Scope**:
- 1 migration and 1 new pure module (`core/review_check.py`);
- 2 new services (`review_service`, `linked_records`);
- 7 new routes and 1 changed (marketer `RequestOut`);
- web: 2 new pages (Pending list, Request review), the admin home filled, and 4 new components
  (LinkedRecordCard, NumbersPinPanel, DecisionPanel, RejectDialog).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | The server decides every accept, reject and pin. A pin re-runs the full check on every source under the 008 locks. Every reason that applies again is recorded. Reasons are only marked, never deleted. A clash gives a warning that needs an explicit, audited confirmation. Status changes only `pending_review → approved/rejected` (§7.2). |
| II. Protection of Identity Documents | ✅ | Review data goes only to `review`. Images are served through the API and every open is logged (R9). Raw readings are never returned. The marketer gets the status and reason only. Pins live in a table read only by review pages. Audit and logs hold no numbers, phone or names (R12). |
| III. Permanent Audit Trail | ✅ | Accept and reject are audited with before and after. A pin is audited by reference (v1.2.1): the entry holds `pin_id`, and the append-only pin row holds the value before and after. Nothing is deleted: reasons are marked, and pins are append-only. |
| IV. Recorded Values Are Immutable | ✅ | The decision (who, when, reason, commission answer, confirmed warnings) is stored on the request. The marketer's values and the original reading are kept unchanged (`submitted_*`, `card_fields`). Prices and username stay as fixed at submission. |
| V. Mobile-First and Arabic | ✅ | Arabic labels and RTL. The review page stacks on a phone. Status colors come from §7.2. |
| VI. Simplicity | ✅ | One pure check function used at pin, read and accept. Decision columns sit on the request, not in a new table. Rejection reasons are a fixed list. The rules went into `docs/system.md` v1.13 first. |
| VII. Fixed Technology Stack | ✅ | No new technology. |
| VIII. Tested Business Rules | ✅ | Unit tests for every type × match × warning. Integration tests for permissions, concurrency, pin re-check, privacy, log and audit safety, and Baghdad-day counts. Playwright for the main flows. |
| IX. Server-Side Authorization | ✅ | Every review route checks `review` on the server (`require_permission`). The home route is open to any admin. The UI menu follows `PAGE_ACCESS`. |
| X. Time Handling | ✅ | `utc_now()` everywhere. The home counts use the Baghdad day and month bounds from `timeutil`. |

Gate result: **pass**. Re-checked after Phase 1: **pass**.

## Project Structure

### Documentation (this feature)

```text
specs/010-admin-request-review/
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
├── migrations/versions/0013_admin_review.py   # decision cols, submitted_*, reason state, pins, image log
├── app/
│   ├── errors.py                     # already_decided, warnings_unconfirmed, … (+ Arabic)
│   ├── core/review_check.py          # new: pure re-check and warnings (R5)
│   ├── core/rejection_reasons.py     # new: codes, labels, note rules (R6)
│   ├── core/timeutil.py              # baghdad_today_bounds
│   ├── models/request.py             # new columns, RequestNumberPin, reason state
│   ├── models/draft.py               # ImageAccessLog.request_id, draft_id nullable
│   ├── schemas/admin_requests.py     # new: list, file, accept, reject, pin, home
│   ├── schemas/requests.py           # rejection fields on RequestOut
│   ├── services/review_service.py    # new: list, file, accept, reject, pin (R1–R7, R13)
│   ├── services/linked_records.py    # new: resolver registry + sijil resolver (R8)
│   ├── services/admin_home.py        # new: counts (R10)
│   ├── services/submit_service.py    # fill submitted_*; rejection fields in to_out
│   ├── api/admin_requests.py         # new routes
│   └── api/admin.py                  # GET /admin/home
└── tests/
    ├── unit/{test_review_check,test_rejection_reasons}.py
    ├── integration/{test_admin_pending_list,test_admin_decide,test_admin_decide_concurrency,
    │               test_admin_pin,test_admin_request_images,test_admin_home,test_migration_0013}.py
    └── integration/{test_marketer_privacy,test_log_safety,test_audit_completeness,test_match_sources}.py  # extended

web/src/
├── lib/adminRequests.ts                     # new: API calls and types
├── lib/labels.ts, lib/auditFormat.ts        # reason, state, rejection and warning labels; audit actions
├── lib/requests.ts                          # rejection fields
├── pages/admin/Home.tsx                     # replaces the placeholder
├── pages/admin/pending/PendingList.tsx      # new
├── pages/admin/pending/RequestReview.tsx    # new (/admin/pending/:id)
├── pages/admin/pending/LinkedRecordCard.tsx
├── pages/admin/pending/NumbersPinPanel.tsx
├── pages/admin/pending/DecisionPanel.tsx    # accept, commission dialog, warning confirmation
├── pages/admin/pending/RejectDialog.tsx
├── pages/marketer/RequestResult.tsx, SubmittedTab.tsx   # «تم رفض الطلب» + reason
└── __tests__/{adminPendingList,decisionPanel,rejectDialog,numbersPinPanel,adminHome}.test.tsx

e2e/tests/admin-review.spec.ts
```

**Structure Decision**: the existing `api/` + `web/` layout and the 008 split:
- pure rules (`review_check`, `rejection_reasons`) go in `core/`;
- the database-facing parts (locks, re-check, resolvers) go in `services/`.

`linked_records` is a registry so 013 and 014 can add `legacy` and `sas` without touching review code.

## Complexity Tracking

No violations.
