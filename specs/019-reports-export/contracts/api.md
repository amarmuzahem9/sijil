# API Contract: Reports and Export (019)

All routes are under `/api/admin`. They use bearer auth and the JSON error format `{code, message}` with Arabic
messages, except `download`, which takes a ticket. A marketer gets `403 forbidden` on every route.

## Shared filter parameters

`period` = `week` | `month` | `range` (required); `from`, `to` = `YYYY-MM-DD` (Baghdad days, required for `range`);
`date_kind` = `submitted` | `linked` (default `submitted`); optional `area_id`, `tower_id`, `marketer_id`, `plan_id`,
`status` (`pending_review|approved|rejected|linked`), `type` (`new|additional|return`).

Errors: `422 period_invalid` «الفترة غير صحيحة» (from > to, a missing date).

## GET /reports/options — `reports`

```json
{ "areas": [{"id": 1, "name": "…", "active": true}],
  "towers": [{"id": 3, "code": "A1", "name": "…", "area_id": 1, "active": true}],
  "plans": [{"id": 2, "name": "…", "active": false}],
  "marketers": [{"id": 9, "name": "…", "archived": false, "active": true}] }
```

## GET /reports/requests — `reports`

The filter parameters plus `page` (default 1).

```json
{ "total": 132, "page": 1, "page_size": 50,
  "rows": [{ "number": 1001, "number_label": "T3C-1001", "name": "…", "deleted": false,
             "tower": "اسم البرج (A1)", "plan": "…", "marketer": "…", "status": "linked", "type": "new",
             "submitted_at": "2026-10-31T20:30:00Z", "linked_at": "2026-11-02T09:00:00Z" }],
  "summary": { "by_status": [{"status": "linked", "count": 90}],
               "by_tower":  [{"tower_id": 3, "tower": "اسم البرج (A1)", "count": 40}],
               "by_marketer": [{"marketer_id": 9, "marketer": "…", "count": 12}] },
  "can_export_identity": true }
```

- `name` is `null` for a deleted row.
- There is never an identity key, image key, amount, rate or payment key (R9, R12).

## POST /exports — `reports`

Body: the filter fields plus `include_identity: bool` (default false).

- `202` returns `ExportOut` with state `preparing`.
- `403 identity_export_forbidden` «تصدير الرقم الوطني والعائلي والصور يحتاج صلاحية المراجعة» when
  `include_identity` is sent without the right (R1).
- `422 no_rows` «لا توجد طلبات بهذه الفلاتر».
- `422 export_too_large` «ضيّق الفلاتر، الحد 5,000 طلب».
- `409 export_in_progress` «عندك تصدير قيد التجهيز».

```json
{ "id": "…", "state": "preparing", "include_identity": true, "row_count": null, "missing_images": null,
  "filters": { … }, "created_at": "…", "ready_at": null, "expires_at": null, "error": null }
```

## GET /exports — `reports`

Lists the caller's own exports from the last 7 days, newest first: `{ "items": [ExportOut] }`. Other admins' exports
never appear.

## GET /exports/{id} — `reports`

`ExportOut`. Another user's export, or an unknown id, gives `404 not_found`.

## POST /exports/{id}/ticket — `reports`, requester only

- `200` returns `{ "url": "/api/admin/exports/<id>/download?ticket=<t>", "expires_in": 60 }`.
- `404` for another user's export.
- `409 export_not_ready` «الملف غير جاهز».
- `410 export_removed` «انتهت صلاحية الملف، صدّره من جديد».
- `403 identity_export_forbidden` when the export holds identity data and the requester has lost `review` or
  `reports`. The export is then removed.

## GET /exports/{id}/download?ticket=… — no bearer

Checks, in order:
1. the ticket hash and its expiry (otherwise `403 ticket_invalid`);
2. the requester is still active and holds `reports` (otherwise `403`);
3. for an identity export, the requester still holds `review` (otherwise the export is removed and `403`);
4. the state is `ready`.

The ticket is cleared first (single use). Before streaming, the route writes `export.downloaded` (with the image
count) and one `image_access_log` row (`purpose = 'export'`) per card image it will send, then streams
`application/zip` with `Content-Disposition: attachment; filename="sijil-requests-YYYY-MM-DD-HHMM.zip"`:
- `requests.xlsx`;
- for an identity export, `cards/T3C-<n>-front.jpg` and `cards/T3C-<n>-back.jpg` for the stored images that still
  exist.

`Cache-Control: no-store`.

## GET /commissions/export?month=YYYY-MM — `commissions`

`200` returns `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, named
`sijil-commissions-YYYY-MM.xlsx`. It has two sheets:
- «العمولات»: marketer, count, «بلا عمولة», tier rate, amount, «تم الدفع»/«غير مدفوع», paid by, paid at, «تراجع بعد
  الدفع» notes, and a total row;
- «الطلبات»: marketer, request number, name, type, tower, link date, «محسوب»/«بلا عمولة»/«مدفوع سابقاً (الشهر)».

There is no national ID, family number, phone or image. The route writes `commissions.exported`. `422 month_invalid`
reuses the 017 error.
