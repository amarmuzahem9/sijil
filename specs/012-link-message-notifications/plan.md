# Implementation Plan: Link Message, Request Statuses and Notifications

**Branch**: `012-link-message-notifications` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**:
- the feature spec `specs/012-link-message-notifications/spec.md`;
- the owner's answers of 2026-11-24: tower line «اسم البرج (رمز البرج)»; deletion notifies the marketer;
  Push is not in 012;
- `docs/system.md` v1.17 §4.3, §4.4, §7.2, §7.4, §8.4;
- the constitution v1.3.1 (no change).

## Summary

After acceptance the marketer must hand the technicians the link message, and learn about admin decisions
without opening every request.

| Part | What |
|---|---|
| Link message | composed on the server from stored columns, returned as `RequestOut.link_message` for approved/linked only; copy and «مشاركة بالواتساب» (`wa.me/?text=`) in the request page (R1–R3) |
| Statuses | one transition table `core/request_status.py`, used by submit/accept/reject and later 013; label «مقبول (بانتظار الربط)» (R4, R9) |
| Notifications | table `notifications` with no personal data, written in the same transaction as accept, reject, delete; list, unread count, read, read-all; badge polled every 15 s (R5–R7) |
| Search | `GET /api/requests?q=` by number, phone or name, own requests only; deleted found by number only (R8) |
| «تم الربط» tab | lists linked requests (empty until 013) (R9) |

Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web). No change.

**Primary Dependencies**: none new (React Query already used for polling and paging).

**Storage**: PostgreSQL 16, migration `0015_notifications` (one table, checks, indexes). See
[data-model.md](./data-model.md).

**Testing**: pytest unit and integration, Vitest, Playwright ([R10](./research.md#r10-tests-principle-viii)).
Each new test is run red before its code.

**Target Platform**: the company Linux server; the marketer app on phones (PWA).

**Project Type**: web app (`api/`, `web/`). No new service.

**Performance Goals**:
- unread count < 50 ms (indexed count), polled every 15 s per open marketer app;
- notification page and search < 1 s for one marketer's data.

**Constraints**:
- No personal data stored in notifications; no national ID, family number, image or OTP in the link message.
- A refused decision writes no notification; one decision writes exactly one.
- Marketers reach only their own requests and notifications.

**Scale/Scope**:
- 1 migration;
- 3 new pure modules (`core/link_message.py`, `core/request_status.py`, `core/request_search.py`);
- 1 new model, 1 new service (`notification_service`), 1 new router (`api/notifications.py`);
- changed: `submit_service` (`to_out` link message, `list_own` search, transition check), `review_service`
  (accept/reject add a notification, transition check), `deletion_service` (adds a notification),
  `schemas/requests.py`, `api/requests.py`, `main.py` (router), `errors.py` (`invalid_transition`,
  `notification_not_found`);
- web: new `lib/notifications.ts`, `lib/linkMessage.ts` (copy/share helpers), `lib/requestSearch.ts`;
  new `pages/marketer/Notifications.tsx` (replaces the placeholder), `components/LinkMessageCard.tsx`;
  changed `MarketerLayout.tsx` (badge), `RequestResult.tsx` (link message), `Requests.tsx` (search box,
  linked tab), `requestStatus.ts` (label), `lib/requests.ts` (types, `q`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | Status changes go through one transition table on the server; refused pairs return 409. Decisions themselves are unchanged. |
| II. Protection of Identity Documents | ✅ | The link message is built server-side from an allow-list of columns; tested never to contain the national ID or family number. Notifications store no personal data; rejection notes are never shown in notifications. Logs keep only numbers and kinds. |
| III. Permanent Audit Trail | ✅ | Decisions stay audited as before. Notifications are not decisions; reading them is not audited. A deletion leaves notifications in place, and they show «محذوف» with no erased data. |
| IV. Recorded Values Are Immutable | ✅ | The link message uses the tower, plan and prices stored at submission. |
| V. Mobile-First and Arabic | ✅ | Arabic texts, RTL; badge in the bottom bar and the side bar; colours from the single `requestStatus.ts`. |
| VI. Simplicity | ✅ | Polling, not live connections; no queue; no stored copy of the message; Push left out by the owner. Rules went into `docs/system.md` 1.17 first. |
| VII. Fixed Technology Stack | ✅ | No new technology or service. |
| VIII. Tested Business Rules | ✅ | Unit tests for every transition pair, the message format and the search classification; integration and e2e tests per R10. |
| IX. Server-Side Authorization | ✅ | Every new route is marketer-only and filters by `marketer_id`; another marketer's ids give 404. |
| X. Time Handling | ✅ | `created_at`/`read_at` in UTC from `utc_now()`, displayed in Baghdad time. |

Gate result: **pass**. Re-checked after Phase 1: **pass**.

## Project Structure

### Documentation (this feature)

```text
specs/012-link-message-notifications/
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
├── migrations/versions/0015_notifications.py
├── app/
│   ├── errors.py                       # invalid_transition, notification_not_found (+ Arabic)
│   ├── core/link_message.py            # new: compose (R1, R2)
│   ├── core/request_status.py          # new: TRANSITIONS, check (R4)
│   ├── core/request_search.py          # new: classify (R8)
│   ├── models/notification.py          # new
│   ├── schemas/notifications.py        # new: NotificationOut, NotificationPage, UnreadCount
│   ├── schemas/requests.py             # RequestOut.link_message
│   ├── services/notification_service.py  # new: add, page, unread_count, mark_read, mark_all
│   ├── services/submit_service.py      # to_out link_message; list_own(q); transition check
│   ├── services/review_service.py      # accept/reject: check + add notification
│   ├── services/deletion_service.py    # add `deleted` notification
│   ├── api/notifications.py            # new router
│   ├── api/requests.py                 # q parameter
│   └── main.py                         # include router
└── tests/
    ├── fixtures/request_search_cases.json
    ├── unit/{test_link_message,test_request_status,test_request_search}.py
    └── integration/{test_notifications,test_link_message_api,test_request_search_api,
                     test_migration_0015}.py
        + extended: test_admin_decide, test_admin_decide_concurrency, test_deletion, test_marketer_privacy

web/src/
├── lib/requestStatus.ts                # «مقبول (بانتظار الربط)»
├── lib/requests.ts                     # link_message, listRequests(statuses, q)
├── lib/notifications.ts                # new: API + titles per kind
├── lib/linkMessage.ts                  # new: copy, whatsappUrl
├── lib/requestSearch.ts                # new: minimum length
├── components/LinkMessageCard.tsx      # new
├── layouts/MarketerLayout.tsx          # unread badge (R6)
├── pages/marketer/Notifications.tsx    # new, replaces placeholder
├── pages/marketer/placeholders.tsx     # drop MarketerNotifications
├── router.tsx                          # /notifications → Notifications
├── pages/marketer/RequestResult.tsx    # LinkMessageCard for approved/linked
├── pages/marketer/Requests.tsx         # search box, linked tab via SubmittedTab
└── __tests__/{linkMessage,notifications,requestSearch,marketerBadge}.test.tsx

e2e/tests/link-message-notifications.spec.ts
```

**Structure Decision**: the existing `api/` + `web/` layout. Pure rules (message text, transitions, search
classification) go in `core/` with unit tests; the notification writes ride inside the existing decision
services so they share the decision's transaction and row lock; the marketer pages reuse React Query.

## Complexity Tracking

No violations.
