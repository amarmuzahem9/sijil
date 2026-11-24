# Data Model: «تم الربط» and the Monthly Counter

**Feature**: 013 | **Migration**: `0016_request_links` (revises `0015`)

## Changed table `requests`

| Column | Type | Rule |
|---|---|---|
| `linked_at` | timestamptz null | the current link time (UTC); set by «تم الربط», cleared by the undo |
| `linked_by` | bigint FK `users.id` null | the admin of the current link; cleared by the undo |

New checks:

- `requests_linked_has_time`: `(status = 'linked') = (linked_at IS NOT NULL AND linked_by IS NOT NULL)`.
- `requests_linked_approved`: `status <> 'linked' OR approved_at IS NOT NULL` (a linked request was accepted).

New partial indexes:

- `requests_awaiting_link` on `(approved_at, id)` where `status = 'approved' AND deleted_at IS NULL`.
- `requests_linked_at` on `(marketer_id, linked_at)` where `status = 'linked'` — the counter and the tab.
- `requests_linked_recent` on `(linked_at DESC, id DESC)` where `status = 'linked'` — the admin recent list.

Untouched by link and undo: `approved_at`, `approved_by`, `counts_commission`, every stored value. The 011
erasure does not list `linked_at`/`linked_by` (a deleted request is never linked).

## New table `request_links` (append-only)

| Column | Type | Rule |
|---|---|---|
| `id` | bigint identity PK | the `link_id` the recent list returns and the undo sends back |
| `request_id` | bigint FK `requests.id` ON DELETE RESTRICT, not null | |
| `kind` | text not null | check `kind IN ('linked','unlinked')` |
| `actor_id` | bigint FK `users.id` not null | the admin |
| `at` | timestamptz not null | UTC |
| `reason` | text null | check: null for `linked`; for `unlinked` one of `not_linked_in_sas`, `by_mistake`, `other_request_linked`, `other` |

Index `request_links_request` on `(request_id, id)`. Rows are never updated or deleted (Principle III). The
current link's id is the newest `linked` row of a linked request; the service reads it under the request's lock.

## Changed table `notifications` (012)

Check `notifications_reason_kind` replaced so `unlinked` needs a reason:
`(kind NOT IN ('approved','linked') OR reason IS NULL) AND (kind NOT IN ('rejected','deleted','unlinked') OR
reason IS NOT NULL)`. Kinds `linked` and `unlinked` are emitted for the first time.

## Status transitions used here (`core/request_status.py`, unchanged)

```
approved ──«تم الربط»──► linked        linked_at, linked_by set; request_links 'linked'; audit request.linked; notification linked
linked ──«التراجع عن الربط»──► approved   linked_* cleared; request_links 'unlinked' + reason; audit request.unlinked; notification unlinked (+ reason)
```

Refusals before any write: deleted → `request_deleted`; already linked → `already_linked`; undo of an approved
row or a stale `link_id` → `already_unlinked`; any other pair → `invalid_transition`.

## Counting rule (derived, not stored)

For a marketer and a Baghdad month `[start, end)`:

- `linked_this_month` = count of their requests with `status='linked'`, `deleted_at IS NULL`,
  `start <= linked_at < end`, `counts_commission = true`;
- `linked_without_commission` = the same with `counts_commission = false`.

A request has at most one `linked_at`, so it counts at most once (FR-012). Admin home: the same condition
without the marketer and without the commission split, by day and by month.

## New pure modules

- `core/unlink_reasons.py`: `LABELS`, `validate(code)`.
- `core/link_search.py`: `classify(q) -> LinkSearchTerm | None` (`number`, `phone`, `username`).
