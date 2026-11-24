# Data Model: Link Message, Request Statuses and Notifications

**Feature**: 012 | **Migration**: `0015_notifications` (revises `0014`)

## New table `notifications`

| Column | Type | Rule |
|---|---|---|
| `id` | bigint identity PK | increases with time; the list's order and paging key |
| `marketer_id` | bigint FK `users.id` ON DELETE RESTRICT, not null | the request's marketer at the event |
| `request_id` | bigint FK `requests.id` ON DELETE RESTRICT, not null | requests are never physically deleted (Principle III) |
| `kind` | text not null | check `kind IN ('approved','rejected','linked','unlinked','deleted')` |
| `reason` | text null | a **code**, never free text: rejection reason code for `rejected`, deletion reason code for `deleted`, 013's undo reason code for `unlinked`; null for `approved`, `linked` |
| `created_at` | timestamptz not null | UTC (Principle X); shown in Baghdad time |
| `read_at` | timestamptz null | set by «read» or «read-all»; never cleared |

Checks and indexes:

- `notifications_reason_kind`: `reason IS NULL` when `kind IN ('approved','linked')`; `reason IS NOT NULL`
  when `kind IN ('rejected','deleted')`.
- `notifications_once` unique partial index on `(request_id, kind)` where `kind IN
  ('approved','rejected','deleted')` — one per decision (FR-017). `linked`/`unlinked` may repeat (013).
- `notifications_marketer_id` on `(marketer_id, id DESC)` for the list.
- `notifications_unread` partial index on `(marketer_id)` where `read_at IS NULL` for the badge.

**No personal data** (FR-019): no name, phone, numbers, address, note. The subscriber's name is read from
`requests.full_name` at display time, which a deletion sets to null (011).

The deletion of a request does not touch its notifications; they now display «محذوف» through the join.

## Model `Notification` (`api/app/models/notification.py`)

Mapped to the table above; relationship `request` (lazy select) for the list query, which joins `requests`
once to read `number`, `full_name`, `deleted_at`.

## Changed: `RequestOut` (`api/app/schemas/requests.py`)

- `link_message: str | None` — composed by `core/link_message.compose` (research R1–R2); non-null only when
  `status IN ('approved','linked')` and the request is not deleted.

## Changed: `GET /api/requests` query

- New optional `q` (research R8). `RequestListItem` is unchanged.

## Status transitions (`api/app/core/request_status.py`)

```
(submission) ──► approved            (auto-accept, no notification)
(submission) ──► pending_review
pending_review ──► approved          notification `approved`
pending_review ──► rejected          notification `rejected` (+ reason code)
approved ──► linked                  013, notification `linked`
linked ──► approved                  013, notification `unlinked` (+ reason code)
pending_review | rejected ──(deletion mark, status kept)── notification `deleted` (+ reason code)
```

Any other pair → `invalid_transition` (409). A deleted request accepts no transition (`request_deleted`, 011).

## Unchanged

`requests` columns and checks, `requests_status`, audit log. Reading or marking a notification is not an
audited action (not a decision or sensitive change, Principle III).
