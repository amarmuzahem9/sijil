# Implementation Plan: Request Check and Decision at Submission

**Branch**: `008-submission-decision` | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-submission-decision/spec.md`; the owner's answers
of 2026-11-23 (Q1 rejected requests do not count, Q2 refuse and keep the draft, Q3 typed numbers go to
review); `docs/system.md` v1.9 §5.4, §5.5, §6, §6.1, §6.2, §7.1–7.3, §8.1, §8.2, §13; constitution.

## Summary

A check engine finds whether a phone, national ID or family number already belongs to a subscriber.
- **Sources**: submitted requests that are pending review, approved or linked. Imported legacy and
  SAS records are added in 013 and 014.
- **Comparison**: the §6.2 keys.
- **Who uses it**:
  - the 007 pre-send check (`precheck_for_otp`): a used phone gets no code;
  - every draft response, for early warnings with no detail about the other subscriber;
  - the new submit call.

**Submission** runs in one transaction:
1. Repeat every check.
2. Lock the three keys.
3. Apply the §6.1 table in order.
4. On a refusal (used phone, existing national ID): keep the draft and audit the attempt.
5. Otherwise: create a `requests` row with the next number `T3C-1001…`. It holds every value fixed,
   the reasons, the username, and the verification time. Then remove the draft.

**Results**:
- approved → «تمت الموافقة» with the username;
- family reason → «بانتظار موافقة المسؤول»;
- edited or hand-typed numbers → «طلبك بانتظار التدقيق».

Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web). Unchanged.

**Primary Dependencies**: none new.

**Storage**: PostgreSQL 16, migration `0010_requests`:
- tables `requests`, `request_reasons` and `request_images`;
- sequence `request_number_seq`;
- column `drafts.additional_confirmed_key`.

See [data-model.md](./data-model.md).

**Testing**:
- pytest unit tests: the decision table, the family key, the numbers-edited rule;
- pytest integration tests: submit, sources, concurrency, the OTP precheck, log safety, audit;
- Vitest;
- Playwright `submit.spec.ts`.

See research R14.

**Target Platform**: the company Linux server; phones (PWA).

**Project Type**: web app (`api/`, `web/`). No new service.

**Performance Goals**:
- submit in under 5 s (SC-001), normally under 1 s;
- early checks within 3 s of a save (SC-005): three indexed lookups.

**Constraints**:
- No subscriber detail in warnings.
- No card data in logs or audit entries.
- Exactly one winner under concurrent submits (SC-004).

**Scale/Scope**:
- Hundreds of requests a month.
- 3 new routes, 3 tables, 1 column.
- 2 new web components and 1 new page.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | The server decides at submission, under advisory locks, against every registered source (R2, R6). The table runs in §6.1 order, and all reasons are stored (`request_reasons`). Comparisons use the §6.2 keys (R3). The verification context is rechecked at submission (R6 step 5). Only allowed transitions are used (R9). |
| II. Protection of Identity Documents | ✅ | Warnings and refusals carry only booleans and codes. Raw readings stay on the server. Images keep their private files. Audit and log lines hold no national ID, family number or full phone (R13). |
| III. Permanent Audit Trail | ✅ | `request.submitted` and `request.submit_refused` are audited. Requests have no delete path. The removed draft's data lives on the request. |
| IV. Recorded Values Are Immutable | ✅ | Prices, names, the readings, the verification time and the automatic decision are copied at submission (R8). `otp_verified_at`, `approved_at` and the later `linked_at` are separate facts. |
| V. Mobile-First and Arabic | ✅ | The messages are Arabic. Autosave is flushed before submitting. The result page works on a phone. The status colors come from `requestStatus.ts`. |
| VI. Simplicity | ✅ | One pure decision function and one source registry. No queue. Only what §6 asks. The rule changes went into `docs/system.md` v1.9 first. |
| VII. Fixed Technology Stack | ✅ | FastAPI, SQLAlchemy, Alembic, PostgreSQL, React. No new service. |
| VIII. Tested Business Rules | ✅ | Every row, combination, key and the concurrency rule have pytest cases. The critical flow has a Playwright test (R14). |
| IX. Server-Side Authorization | ✅ | Submit and the request routes check the owner and the active marketer. Others get 404. |
| X. Time Handling | ✅ | Times are UTC from `utc_now()`. The expired card uses Baghdad's date (the 006 rule, rechecked at submit). |

Gate result: **pass**. Re-checked after Phase 1: **pass**.

## Project Structure

### Documentation (this feature)

```text
specs/008-submission-decision/
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
├── migrations/versions/0010_requests.py        # new: requests, request_reasons, request_images, sequence, drafts.additional_confirmed_key
├── app/
│   ├── errors.py                               # phone_used, national_id_exists, no_family_match, draft_incomplete, otp_needs_reverify, catalog_changed, request_not_found
│   ├── core/family_key.py                      # new: §6.2 family comparison key
│   ├── core/decision.py                        # new: pure §6.1 decide()
│   ├── models/request.py                       # new: Request, RequestReason, RequestImage
│   ├── models/draft.py                         # additional_confirmed_key
│   ├── schemas/drafts.py                       # DraftOut.checks, PATCH additional_confirmed
│   ├── schemas/requests.py                     # new: RequestOut, RequestListItem, SubmitIn
│   ├── services/match_service.py               # new: source registry, find_matches, sijil source
│   ├── services/numbers_edited.py              # new: row 4 rule (R4)
│   ├── services/submit_service.py              # new: the submission transaction (R6)
│   ├── services/phone_checks.py                # precheck_for_otp → phone_used
│   ├── services/draft_service.py               # checks + new missing items in to_out; confirmation; referenced_file_names
│   ├── services/settings_service.py            # usage checks registered for requests (R9)
│   ├── api/drafts.py                           # POST /drafts/{id}/submit
│   └── api/requests.py                         # new: GET /requests, GET /requests/{id}
└── tests/
    ├── unit/test_decision.py
    ├── unit/test_family_key.py                 # + fixtures/family_key_cases.json
    ├── unit/test_numbers_edited.py
    ├── integration/test_submit.py
    ├── integration/test_match_sources.py
    ├── integration/test_submit_concurrency.py
    ├── integration/test_otp.py                 # extended: real phone_used
    ├── integration/test_log_safety.py          # extended
    └── integration/test_audit_completeness.py  # extended

web/src/
├── lib/requests.ts                             # new: submit, list, get; error → Arabic text
├── lib/draftValidation.ts                      # labels for the 3 server-only missing items
├── lib/labels.ts                               # audit action labels
├── pages/marketer/subscriber/MissingSummary.tsx    # «إرسال» enabled; flush then submit
├── pages/marketer/subscriber/FamilyMatchNotice.tsx # new: message + «طلب اشتراك إضافي»
├── pages/marketer/subscriber/CardDataSection.tsx   # shows national ID / family notices
├── pages/marketer/subscriber/PhoneSection.tsx      # shows phone_used
├── pages/marketer/RequestResult.tsx            # new: /requests/:id
├── pages/marketer/Requests.tsx                 # «بالانتظار», «مقبولة» lists
└── __tests__/{missingSummarySubmit,requestResult,familyMatchNotice}.test.tsx

e2e/tests/submit.spec.ts
```

**Structure Decision**: the existing `api/` + `web/` layout:
- pure rules go in `core/` (decision, family key);
- the DB-facing engine and the transaction go in `services/`;
- the source registry follows the 004 usage-registry pattern, so 013 and 014 plug in without
  touching the rules.

## Complexity Tracking

No violations.
