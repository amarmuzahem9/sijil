# Implementation Plan: «تم الربط» and the Monthly Counter

**Branch**: `013-linking-counter` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**:
- the feature spec `specs/013-linking-counter/spec.md`;
- the owner's answers of 2026-11-24: the counter counts links counted for commission, with «و M بلا عمولة»
  under it; a re-link counts in the month of the new link; fixed undo reasons, «سبب آخر» without text; the
  spec assumptions approved;
- `docs/system.md` v1.18 §4.2, §4.3, §4.4, §6.4, §6.5, §7.2, §7.4, §9, §10 items 1 and 3;
- the constitution v1.3.1 (no change).

## Summary

The admin confirms that an accepted request is connected in SAS, or undoes that with a reason; the marketer's
monthly counter, the «تم الربط» tab and the admin home finally count real links.

| Part | What |
|---|---|
| Link state | `requests.linked_at`/`linked_by` for the current link; append-only `request_links` for every link and undo (R1) |
| Actions | `POST …/link` and `POST …/unlink` (reason + `link_id`), row lock, transition check, audit and notification in the same transaction (R2, R3) |
| Undo reasons | fixed list `core/unlink_reasons.py`, no free text (R4) |
| «بانتظار الربط» page | two lists (waiting, recent links), allow-list rows without identity data, search by number, phone or username (R7) |
| Counter | marketer dashboard: commission links this Baghdad month, «و M بلا عمولة», latest 10 links (R5); admin home linked counts (R6) |
| Marketer views | `linked_at` on list and request; the «تم الربط» tab ordered by link time (R8) |
| Deleted requests | refused first, excluded from lists and counts, deletion of linked/undone refused and tested (R9) |

Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web). No change.

**Primary Dependencies**: none new (FastAPI, SQLAlchemy 2, Alembic, MUI, React Query already used).

**Storage**: PostgreSQL 16, migration `0016_request_links`: two columns, two checks and three partial indexes
on `requests`; table `request_links`; the `notifications_reason_kind` check replaced. See
[data-model.md](./data-model.md).

**Testing**: pytest unit and integration, Vitest, Playwright ([R12](./research.md#r12-tests-principle-viii)).
Each new test is run red before its code.

**Target Platform**: the company Linux server; the admin panel in the browser; the marketer app on phones (PWA).

**Project Type**: web app (`api/`, `web/`). No new service.

**Performance Goals**:
- dashboard counts and admin home < 100 ms (partial indexes on linked rows);
- «بانتظار الربط» lists and search < 1 s with a few thousand accepted requests.

**Constraints**:
- A refused link or undo writes nothing (status, history, audit, notification).
- `link`-only admins never receive identity numbers, card fields or images.
- Month boundaries at Baghdad midnight; storage in UTC.
- A request counts at most once.

**Scale/Scope**:
- 1 migration;
- 2 new pure modules (`core/unlink_reasons.py`, `core/link_search.py`);
- 1 new model (`RequestLink`), 1 new service (`link_service`: lists, link, unlink, dashboard counts), 1 new
  router (`api/admin_links.py`);
- changed: `models/request.py` (columns, checks), `models/notification.py` (check),
  `services/notification_service.py` (undo labels), `services/admin_home.py` (linked), `api/marketer.py`
  (dashboard), `services/submit_service.py` (`linked_at`, tab order), `schemas/requests.py`, new
  `schemas/admin_links.py`, `errors.py` (`already_linked`, `already_unlinked`), `main.py` (router);
- web: new `lib/links.ts`, `pages/admin/links/AwaitingLink.tsx`, `LinkConfirmDialog.tsx`, `UnlinkDialog.tsx`;
  changed `placeholders.tsx` and `router.tsx` (real page), `labels.ts` (undo reasons, audit actions),
  `auditFormat.ts` (reason), `pages/marketer/Dashboard.tsx` (counter, «بلا عمولة», latest links),
  `SubmittedTab.tsx` (link date), `RequestResult.tsx` (link date), `lib/requests.ts` (`linked_at`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | Link and undo go through `request_status.check` under a row lock; refused pairs answer 409. The checks and decisions of 008–010 are unchanged. |
| II. Protection of Identity Documents | ✅ | The admin link rows come from an allow-list schema with no identity number, card field or image; tested. Undo reasons are codes without text, so no personal data reaches notifications or the audit. Logs keep action and number only. |
| III. Permanent Audit Trail | ✅ | `request.linked` and `request.unlinked` audited with who, when, before/after and the reason; every link and undo kept in append-only `request_links`. Accepted and linked requests stay non-deletable. |
| IV. Recorded Values Are Immutable | ✅ | Link completion has its own time (`linked_at`), separate from `approved_at`; undo never touches the acceptance or `counts_commission`. The paid-month lock is 017's. |
| V. Mobile-First and Arabic | ✅ | Arabic texts, RTL; green «تم الربط» from the single `requestStatus.ts`; the dashboard stays phone-first. |
| VI. Simplicity | ✅ | One column for the current link, one history table, offset paging, no polling added. Rules went into `docs/system.md` 1.18 first. |
| VII. Fixed Technology Stack | ✅ | No new technology or service. |
| VIII. Tested Business Rules | ✅ | Every link/undo refusal, concurrency, month boundaries, commission split and the once-only rule have tests (R12). |
| IX. Server-Side Authorization | ✅ | Admin routes `require_permission("link")`; marketer counts filtered by `marketer_id`; the marketer never gets `linked_by`. |
| X. Time Handling | ✅ | `linked_at` and history times in UTC from `utc_now()`; months from `baghdad_month_bounds()`; boundary tests with the test clock. |

Gate result: **pass**. Re-checked after Phase 1: **pass**.

## Project Structure

### Documentation (this feature)

```text
specs/013-linking-counter/
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
├── migrations/versions/0016_request_links.py
├── app/
│   ├── errors.py                         # already_linked, already_unlinked (+ Arabic)
│   ├── core/unlink_reasons.py            # new: LABELS, validate (R4)
│   ├── core/link_search.py               # new: classify (R7)
│   ├── models/request.py                 # linked_at, linked_by, checks, indexes
│   ├── models/request_link.py            # new: RequestLink
│   ├── models/notification.py            # check: unlinked needs a reason
│   ├── schemas/admin_links.py            # new: LinkRow, LinkList, UnlinkIn
│   ├── schemas/requests.py               # linked_at on RequestOut and RequestListItem
│   ├── services/link_service.py          # new: awaiting, recent, link, unlink, marketer_counts
│   ├── services/notification_service.py  # _REASON_LABELS["unlinked"]
│   ├── services/admin_home.py            # linked by linked_at
│   ├── services/submit_service.py        # linked_at out; linked tab order
│   ├── api/admin_links.py                # new router
│   ├── api/marketer.py                   # dashboard from link_service
│   └── main.py                           # include router
└── tests/
    ├── fixtures/link_search_cases.json
    ├── unit/{test_unlink_reasons,test_link_search}.py
    └── integration/{test_link,test_unlink,test_link_lists,test_linked_counter,test_migration_0016}.py
        + extended: test_admin_home, test_deletion, test_notifications, test_marketer_privacy

web/src/
├── lib/links.ts                          # new: API, types
├── lib/labels.ts                         # UNLINK_REASON_LABELS, audit actions
├── lib/auditFormat.ts                    # undo reason
├── lib/requests.ts                       # linked_at
├── pages/admin/links/AwaitingLink.tsx    # new: tabs, search, rows
├── pages/admin/links/LinkConfirmDialog.tsx
├── pages/admin/links/UnlinkDialog.tsx
├── pages/admin/placeholders.tsx          # drop AdminAwaitingLink
├── router.tsx                            # /admin/awaiting-link → AwaitingLink
├── pages/marketer/Dashboard.tsx          # counter, «و M بلا عمولة», latest links
├── pages/marketer/SubmittedTab.tsx       # link date in the linked tab
├── pages/marketer/RequestResult.tsx      # «تاريخ الربط»
└── __tests__/{awaitingLink,unlinkDialog,dashboard,linkedTab}.test.tsx

e2e/tests/linking-counter.spec.ts
```

**Structure Decision**: the existing `api/` + `web/` layout. Linking gets its own service and router instead of
growing `review_service`, because its permission (`link`) and its page differ from review; it reuses the same
lock pattern, `request_status.check`, `audit_service` and `notification_service`.

## Complexity Tracking

No violations.
