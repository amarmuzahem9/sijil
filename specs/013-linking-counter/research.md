# Research: «تم الربط» and the Monthly Counter

**Feature**: 013 | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

No new dependency and no new service. Every decision reuses what 010–012 built: the row lock of the
decisions, `request_status.check`, `audit_service.record`, `notification_service.add`, the Baghdad month bounds
of `core/timeutil.py`, and the request number and phone parsers.

## R1. Current link on the request, history in its own table

- **Decision**: `requests` gains `linked_at` and `linked_by`, set by «تم الربط» and cleared by the undo. A new
  append-only table `request_links` keeps every link and every undo (request, kind, actor, time, undo reason
  code). See [data-model.md](./data-model.md).
- **Rationale**: the counter, the «تم الربط» tab order and the admin home count all need "the current link
  time" (owner, Q2: a re-link counts in the month of the new link). One nullable column answers that with
  one indexed condition. FR-022 and Principle III want each event kept and never edited; a second table does
  that without making the request row carry a list. Principle IV ("link completion is its own fact with its own
  time") is met by `linked_at` staying separate from `approved_at`, which the undo never touches.
- **Alternatives**: reading the current link from the last `request_links` row — rejected: every count and
  list would need a lateral join. Keeping `linked_at` after an undo and adding `unlinked_at` — rejected: two
  columns to combine everywhere, and the re-link would have to overwrite them anyway.

## R2. Lock, transition check and the "already" answers

- **Decision**: `link_service._lock(db, request_id)` reads the row `FOR UPDATE OF requests` with
  `populate_existing`, like `review_service._lock_pending`. Then, in this order:
  1. missing → `404 request_not_found`;
  2. deleted → `409 request_deleted` (011);
  3. link: status `linked` → `409 already_linked` «تم ربط هذا الطلب مسبقاً»; any other non-`approved` status →
     `request_status.check` raises `409 invalid_transition`;
  4. undo: the body carries the `link_id` the page showed; status `approved`, or a current link whose id is
     not `link_id` → `409 already_unlinked` «تم التراجع عن هذا الربط مسبقاً»; status `pending_review` or
     `rejected` → `invalid_transition`.
- **Rationale**: the second of two concurrent admins waits on the lock and then sees the first change, so it
  writes no notification and no audit (FR-006, FR-009, SC-004). The `link_id` on the undo stops a stale page
  from undoing a newer link made by another admin after it loaded.
- Permission: the router uses `require_permission("link")`, so any other caller gets `403 forbidden` before
  the lock (FR-001, Principle IX).

## R3. One transaction per action

Link: set `status='linked'`, `linked_at=now`, `linked_by`, `updated_at`; add a `request_links` row (`linked`);
`audit_service.record(action="request.linked", before={"status":"approved"}, after={"status":"linked"},
entity_id=<number>)`; `notification_service.add(db, request, "linked")`; commit.

Undo: set `status='approved'`, `linked_at=NULL`, `linked_by=NULL`; add a `request_links` row (`unlinked`,
reason); audit `request.unlinked` with `after={"status":"approved","reason":<code>}`;
`notification_service.add(db, request, "unlinked", <code>)`; commit. `approved_at`, `approved_by` and
`counts_commission` stay (FR-010).

Logs carry the action and the request number only (Principle II).

## R4. Undo reasons

`api/app/core/unlink_reasons.py`, mirrored in `web/src/lib/labels.ts`, like `deletion_reasons.py`:

| Code | Label |
|---|---|
| `not_linked_in_sas` | لم يُربط فعلياً في SAS |
| `by_mistake` | ضُغط بالخطأ |
| `other_request_linked` | ربط طلب آخر بدله |
| `other` | سبب آخر |

No free text for any code (owner, Q3). `notification_service._REASON_LABELS["unlinked"]` gets this table, so
the notification shows the label.

## R5. The marketer counter

- **Decision**: `GET /api/marketer/dashboard` computes, for the caller, over requests with `status='linked'`,
  `deleted_at IS NULL` and `linked_at` inside `baghdad_month_bounds()`:
  - `linked_this_month` = rows with `counts_commission = true`;
  - `linked_without_commission` = rows with `counts_commission = false` (only returns accepted with «لا»);
  - `recent_links` = up to 10 rows, `linked_at DESC, id DESC`: id, number label, full name, link time.
  The web shows «تم الربط هذا الشهر: N» and, when M > 0, «و M بلا عمولة» under it (owner, Q1).
- **Counted once** (FR-012): a request has at most one current `linked_at`, so it is in at most one month and
  appears once, whatever its history. An undo removes it from every month; a re-link puts it in the new
  month (owner, Q2).
- **Refresh**: the home query keeps React Query's refetch on focus and remount; no polling (spec
  assumption). The notification badge keeps its 15 s poll (012).
- **Alternatives**: counting from `request_links` events — rejected: needs "last event per request" and gives
  the same answer as R1's column.

## R6. Admin home

`admin_home._row` replaces the fixed `linked=0` with the count of `status='linked'` rows whose `linked_at` is
in the day or month bounds (all marketers, deleted rows cannot be linked). Same function as the other counts.

## R7. «بانتظار الربط» page: two lists and a search

- `GET /api/admin/links/awaiting?q=&offset=&limit=` — `status='approved'`, not deleted, `approved_at ASC,
  id ASC` (oldest acceptance first, FR-002).
- `GET /api/admin/links/recent?q=&offset=&limit=` — `status='linked'`, not deleted, `linked_at DESC, id DESC`,
  every month (spec assumption), each row with link time, who linked, and the current `link_id`.
- Rows carry only: id, number label, full name, username, phone, tower name and code, plan name, marketer
  current name, approval time (plus link time, linker name and `link_id` in the recent list). No identity
  number, no card field, no image (FR-002, SC-005). A dedicated schema `LinkRow` makes that an allow-list.
- Paging by `offset`/`limit` (default 50, max 100): the lists are hundreds of rows at most for a single company;
  keyset paging is not needed (Principle VI).
- **Search** `core/link_search.classify(q)`: request number (`request_number.parse`) → phone
  (`normalize_phone`) → username (trimmed, upper-cased, matches `^[A-Z0-9-]+-07\d{9}$`, compared with
  `upper(username)`) → otherwise no match. Fewer than 2 characters → `422`. Unit-tested from a fixture file
  like `request_search`.
- **Alternatives**: one list with a status filter — rejected: the two lists have different orders and the
  undo button belongs only to one. Showing the link message to the admin — not asked (spec assumption).

## R8. The marketer «تم الربط» tab and request page

- `RequestListItem` and `RequestOut` gain `linked_at` (null unless linked; null on a deleted row).
- `submit_service.list_own` orders by `linked_at DESC, id DESC` when the requested statuses are exactly
  `['linked']`, else by submission as today (FR-017). Search results keep the submission order.
- The request page shows «تاريخ الربط» for a linked request; the link message stays (012). An undone request
  shows `approved` again and leaves the tab by its status.
- The marketer never receives `linked_by` (FR-019).

## R9. Deleted requests

- Only `pending_review` and `rejected` requests are deletable (011, `DELETABLE_STATUSES`), so a deleted row is
  never `approved` or `linked`. Still: the lock refuses `request_deleted` first (R2), both admin lists and every
  count filter `deleted_at IS NULL`, and the dashboard query too (FR-020).
- New tests with real linked rows: deleting a linked request and an undone (approved again) request answer
  `request_not_deletable` and change nothing.
- A database check `requests_linked_has_time` (`(status = 'linked') = (linked_at IS NOT NULL AND linked_by IS
  NOT NULL)`) and `requests_linked_approved` (`status <> 'linked' OR approved_at IS NOT NULL`) back the rules.
  An erasure (011) never touches `linked_*`, and a deleted row can never satisfy `status='linked'` through the
  service.

## R10. Audit labels

`web/src/lib/labels.ts` gains `'request.linked': 'تم الربط'` and `'request.unlinked': 'تراجع عن الربط'`;
`auditFormat.ts` shows the undo reason label from `after.reason`. Constitution III already lists «linked» and
«undo linked» as audited actions.

## R11. Notifications table check

Migration `0016` replaces `notifications_reason_kind` so `unlinked` also needs a reason:
`(kind NOT IN ('approved','linked') OR reason IS NULL) AND (kind NOT IN ('rejected','deleted','unlinked') OR
reason IS NOT NULL)`. The partial unique index stays as it is: `linked` and `unlinked` may repeat (012
data-model).

## R12. Tests (Principle VIII)

| Level | What |
|---|---|
| pytest unit | `unlink_reasons` labels and validation; `link_search.classify` from `fixtures/link_search_cases.json`; `request_status` link/undo pairs already covered (012), extended with the deleted cases at service level |
| pytest integration | link: success writes status, time, history row, audit, one notification; refused for pending, rejected, deleted, linked, missing, no permission (403), marketer; concurrent links: one wins. Undo: reason required and validated, success restores `approved` and keeps acceptance and commission; stale `link_id`, double undo, not linked refused. Counter: commission vs without commission, month boundaries at Baghdad midnight (clock fixture), undo of a previous month, re-link in a new month counts once, other marketers excluded. Admin home linked by day and month. Lists: order, search by number/phone/username, no identity fields in the JSON, deleted excluded. Deletion of linked and undone requests refused. Migration 0016 up/down |
| Vitest | dashboard counter with and without «و M بلا عمولة», recent links list; awaiting page tabs, search, link confirm, undo dialog with the reason list; marketer linked tab with link date |
| Playwright | `linking-counter.spec.ts`: accept → admin links → marketer badge and counter 1 → admin undoes with a reason → counter 0, notification with the reason → relink → counter 1 |

Each new test is run red first (project rule).
