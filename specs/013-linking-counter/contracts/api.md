# API Contract: 013

Admin routes need the main admin or an admin with `link` (`require_permission("link")`): `403 forbidden`
otherwise, for marketers too. Marketer routes stay `require_roles("marketer")` and read only the caller's rows.
Times are UTC ISO 8601.

## New: `GET /api/admin/links/awaiting?q=&offset=0&limit=50`

Accepted, not linked, not deleted; oldest acceptance first. `limit` 1–100.

```json
{
  "items": [
    {
      "id": 17,
      "number_label": "T3C-1017",
      "full_name": "أحمد علي حسين",
      "username": "ALM03-07801234567",
      "phone": "07801234567",
      "tower_name": "العلم 3",
      "tower_code": "ALM03",
      "plan_name": "PLUS",
      "marketer_name": "علي",
      "approved_at": "2026-11-24T09:12:00Z",
      "linked_at": null,
      "linked_by_name": null,
      "link_id": null
    }
  ],
  "total": 1
}
```

- No national ID, family number, card field or image link in any row (allow-list schema `LinkRow`).
- `q` (≥ 2 characters after trimming): request number (with or without «T3C-», any digits), phone (any
  §8.1 form) or username (case-insensitive). Anything else gives no rows. Shorter → `422 validation_error`.

## New: `GET /api/admin/links/recent?q=&offset=0&limit=50`

Linked, not deleted; newest link first; every month. Same row shape, with `linked_at`, `linked_by_name` and
`link_id` (the current link) filled. Same `q`.

## New: `POST /api/admin/requests/{id}/link`

Body: none. `200` with the `LinkRow` of the now linked request.

Effects in one transaction: status `linked`, `linked_at`, `linked_by`; a `request_links` row; audit
`request.linked` (`before {"status":"approved"}`, `after {"status":"linked"}`, entity = request number); one
notification `linked` for the marketer.

| Error | When |
|---|---|
| `404 request_not_found` | unknown id |
| `409 request_deleted` | deleted request |
| `409 already_linked` «تم ربط هذا الطلب مسبقاً» | already linked (also the second of two concurrent calls) |
| `409 invalid_transition` | pending review or rejected |

## New: `POST /api/admin/requests/{id}/unlink`

```json
{ "reason": "by_mistake", "link_id": 88 }
```

`reason` ∈ `not_linked_in_sas`, `by_mistake`, `other_request_linked`, `other`; no free text. `200` with the
`LinkRow` of the request, now accepted.

Effects in one transaction: status `approved`, `linked_at`/`linked_by` cleared; a `request_links` row
`unlinked` with the reason; audit `request.unlinked` (`after {"status":"approved","reason":…}`); one
notification `unlinked` with the reason code. Acceptance and `counts_commission` unchanged.

| Error | When |
|---|---|
| `422 validation_error` | missing or unknown reason, missing `link_id` |
| `404 request_not_found` | unknown id |
| `409 request_deleted` | deleted request |
| `409 already_unlinked` «تم التراجع عن هذا الربط مسبقاً» | not linked any more, or `link_id` is not the current link |
| `409 invalid_transition` | pending review or rejected |

A refused call writes nothing: no status change, no history row, no audit, no notification.

## Changed: `GET /api/marketer/dashboard`

```json
{
  "linked_this_month": 27,
  "linked_without_commission": 1,
  "month_label": "تشرين الثاني 2026",
  "recent_links": [
    { "id": 17, "number_label": "T3C-1017", "full_name": "أحمد علي حسين", "linked_at": "2026-11-24T09:30:00Z" }
  ]
}
```

- Counts per [data-model.md › Counting rule](../data-model.md#counting-rule-derived-not-stored); Baghdad month.
- `recent_links`: up to 10 of this month, newest link first, the caller's only.

## Changed: `GET /api/requests` and `GET /api/requests/{id}`

`RequestListItem` and `RequestOut` gain `linked_at` (null unless linked). With `status=linked` alone, the list
is ordered by `linked_at` newest first. No `linked_by` for the marketer.

## Changed: `GET /api/admin/home`

`today.linked` and `month.linked` count requests currently linked with `linked_at` in that Baghdad day or month.

## Changed: `POST /api/admin/requests/{id}/delete` (011)

Unchanged rule, now tested on real rows: linked and undone (accepted) requests → `409 request_not_deletable`.

## Notifications (012)

`GET /api/notifications` now returns `linked` (no reason) and `unlinked` rows; `reason_label` of `unlinked` is
the fixed label of [research R4](../research.md#r4-undo-reasons).
