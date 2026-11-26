# Implementation Plan: Subscriber File and Search

**Branch**: `018-subscriber-file-search` | **Date**: 2026-11-26 | **Spec**: [spec.md](./spec.md)

**Input**:
- the feature spec `specs/018-subscriber-file-search/spec.md`;
- the owner's answers of 2026-11-26: one file per record with its linked records and their reasons, no merged person
  (Q1: A); identity numbers, card fields, images and the search by them for the main admin and `review` only
  (Q2: A); the file is read-only (Q3: A); the spec assumptions approved;
- `docs/system.md` v1.24 §3.1, §4.3, §6.1, §6.2, §6.4, §7.4, §8.1, §10 item 4, §12.1, §12.2, §13;
- the constitution v1.4.0 (no change).

## Summary

«المشتركون» stops being a placeholder: one search box over Sijil requests, legacy and SAS subscribers, and a
read-only file per record listing the records linked to it, shown per permission.

| Part | What |
|---|---|
| Search kinds | pure `core/subscriber_search.py`: number, legacy number, national ID, phone, family, username, name (R2) |
| Name folding | `fold_arabic` in `core/arabic_name.py`, the same folding in SQL (R3) |
| Search | one capped query per source, merged newest first, 50 per page; identity kinds refused without `review` before any query (R2, R4) |
| File | the record, its linked records with the strongest reason, the request history from stored facts (R5, R9) |
| Deleted | found by number only, «سجل محذوف» with kept fields (R6) |
| Permissions | allow-list schemas, identity keys absent for `link`/`reports` (R7) |
| Images | existing review routes, already logged (R8) |
| Pages | `/admin/subscribers` and `/admin/subscribers/:source/:ref` (R10) |

Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web). No change.

**Primary Dependencies**: none new.

**Storage**: PostgreSQL 16, **no migration** (read-only feature). See [data-model.md](./data-model.md).

**Testing**: pytest unit and integration, Vitest (from PowerShell), Playwright ([R12](./research.md#r12-tests-principle-viii)).
Each new test is run red before its code.

**Target Platform**: the company Linux server; the admin panel in the browser.

**Project Type**: web app (`api/`, `web/`). No new service.

**Performance Goals**: with 20,000 SAS rows, 500 legacy rows and 5,000 requests: a search page < 1 s (SC-001), a file
with up to 20 linked records < 1 s (SC-002).

**Constraints**:
- No identity number, card field or image reaches a caller without `review` (and not main admin), in results or files.
- An identity-kind search without `review` is refused before any lookup, the same for existing and unknown numbers.
- No marketer access; the marketer's own search unchanged.
- Read-only: no write route; logs carry kind and `source:ref` only.

**Scale/Scope**:
- 0 migrations; 1 new pure module (`core/subscriber_search.py`), 1 changed (`core/arabic_name.py`: `fold_arabic`);
- 2 new services (`services/subscriber_search.py`, `services/subscriber_file.py`), 1 new router
  (`api/admin_subscribers.py`), 1 schema module (`schemas/subscribers.py`), `errors.py` (2 codes), `main.py`;
- web: new `lib/subscribers.ts`, `pages/admin/subscribers/{SubscriberSearch,SubscriberFile}.tsx`; changed
  `router.tsx` (replace placeholder, add the file route), `pages/admin/placeholders.tsx` (drop `AdminSubscribers`),
  `lib/labels.ts` (sources, link reasons, history kinds).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | The check engine and decisions are untouched; the file uses the same keys and normalizations (§6.2) for display only. |
| II. Protection of Identity Documents | ✅ | Allow-list schemas; identity keys absent for `link`/`reports`; identity-kind search refused without `review`; images only through the existing logged routes; logs carry no values. |
| III. Permanent Audit Trail | ✅ | Read-only feature; every image open logged (existing); nothing is written or deleted. |
| IV. Recorded Values Are Immutable | ✅ | Nothing is changed (Q3). History is read from the stored facts. |
| V. Mobile-First and Arabic | ✅ | Arabic, RTL; status colors from `requestStatus.ts`; the list works at phone width. |
| VI. Simplicity | ✅ | No migration, no extension, no new service; folding on read at this size. Rules in `docs/system.md` 1.24 first. |
| VII. Fixed Technology Stack | ✅ | No new technology. |
| VIII. Tested Business Rules | ✅ | Classifier fixture, folding, every kind across sources, permission key sets, deleted, read-only, performance (R12). |
| IX. Server-Side Authorization | ✅ | `require_permission("review", "link", "reports")`; identity fields and kinds checked on the server per caller; marketers refused. |
| X. Time Handling | ✅ | Times stored UTC, shown in Baghdad time; no month logic. |

Gate result: **pass**. Re-checked after Phase 1: **pass**.

## Project Structure

### Documentation (this feature)

```text
specs/018-subscriber-file-search/
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
├── app/
│   ├── errors.py                         # search_unclear, identity_search_forbidden
│   ├── core/arabic_name.py               # fold_arabic
│   ├── core/subscriber_search.py         # new: Term, classify (R2)
│   ├── schemas/subscribers.py            # new: ResultRow, SearchOut, FileOut (per-permission)
│   ├── services/subscriber_search.py     # new: per-source queries, merge, paging (R4)
│   ├── services/subscriber_file.py       # new: record, linked, history (R5, R9)
│   ├── api/admin_subscribers.py          # new router
│   └── main.py                           # include router
└── tests/
    ├── fixtures/subscriber_search_cases.json
    ├── unit/{test_subscriber_search,test_arabic_fold}.py
    └── integration/{test_subscriber_search_api,test_subscriber_file,test_subscriber_privacy,
                     test_subscriber_performance}.py

web/src/
├── lib/subscribers.ts
├── lib/labels.ts                         # source, link reason, history labels
├── pages/admin/subscribers/{SubscriberSearch,SubscriberFile}.tsx
├── pages/admin/placeholders.tsx          # AdminSubscribers removed
├── router.tsx
└── __tests__/{subscriberSearch,subscriberFile}.test.tsx

api/tests/e2e_subscriber_seed.py          # synthetic legacy/SAS/requests for the e2e
scripts/e2e.sh                            # runs the seed
e2e/tests/subscriber-file.spec.ts
```

**Structure Decision**: the existing `api/` + `web/` layout. Search and file are two services (one lists across
sources, the other builds one record's view) behind one router; they reuse `request_number`, `normalize_phone`,
`family_key`, `clean_arabic_name` and the existing image routes.

## Complexity Tracking

No violations.
