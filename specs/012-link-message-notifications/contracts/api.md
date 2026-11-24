# API Contract: 012

All routes are marketer-only (`require_roles("marketer")`), act on the caller's own rows, and answer 404 for
anything else (Principle IX). Times are UTC ISO 8601.

## Changed: `GET /api/requests/{id}` and `POST /api/drafts/{id}/submit`

`RequestOut` gains:

```json
{ "link_message": "طلب ربط جديد | رقم الطلب: #T3C-1001\nالاسم: …\n…\nالمسوّق: …" }
```

`null` unless `status` is `approved` or `linked` and the request is not deleted. Format: research R2.

## Changed: `GET /api/requests?status=…&q=…`

- `q` (optional, ≥ 2 characters after trimming): a request number, a phone, or part of the subscriber's name
  (research R8). With `q`, `status` may be omitted to search all statuses.
- Response unchanged: `{ "items": RequestListItem[] }`. A deleted request matches only by number.
- `q` shorter than 2 characters → `422 validation_error`.

## New: `GET /api/notifications?before=<id>&limit=<n>`

`limit` 1–50, default 30. Newest first.

```json
{
  "items": [
    {
      "id": 41,
      "kind": "rejected",
      "request_id": 17,
      "number_label": "T3C-1017",
      "full_name": "أحمد علي حسين",
      "deleted": false,
      "reason_label": "صورة البطاقة غير واضحة",
      "created_at": "2026-11-24T09:12:00Z",
      "read_at": null
    }
  ],
  "next_before": 12
}
```

- `full_name` is `null` and `deleted` is `true` when the request was deleted.
- `reason_label`: the fixed Arabic label of the reason code («سبب آخر» for `other`, never the admin's note);
  `null` for `approved` and `linked`.
- `next_before` is `null` on the last page.

The web shows the title from `kind`: `approved` «تمت الموافقة على الطلب»، `rejected` «تم رفض الطلب»، `linked`
«تم ربط المشترك»، `unlinked` «تم التراجع عن الربط»، `deleted` «تم حذف الطلب».

## New: `GET /api/notifications/unread-count`

```json
{ "count": 3 }
```

## New: `POST /api/notifications/{id}/read`

`204`. Idempotent; an already read row keeps its first `read_at`. Another marketer's id → `404
notification_not_found`.

## New: `POST /api/notifications/read-all`

`204`. Marks all the caller's unread rows.

## Side effects of existing admin routes

| Route | New effect |
|---|---|
| `POST /api/admin/requests/{id}/accept` | adds one `approved` notification in the same transaction |
| `POST /api/admin/requests/{id}/reject` | adds one `rejected` notification with the reason code |
| `POST /api/admin/requests/{id}/delete` | adds one `deleted` notification with the deletion reason code |

A refused call (409 `already_decided`, `request_deleted`, `request_not_deletable`, `warnings_unconfirmed`,
422) adds nothing. Response bodies are unchanged.
