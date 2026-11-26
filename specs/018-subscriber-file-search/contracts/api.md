# API Contract: 018

Both routes need the main admin or an admin with `review`, `link` or `reports`
(`require_permission("review", "link", "reports")`): `403 forbidden` otherwise, marketers included. Read-only: any
other method answers 405. Times are UTC ISO 8601.

## New: `GET /api/admin/subscribers?q=&offset=0&limit=50`

`limit` 1–50. `q` is classified (research R2).

```json
{
  "kind": "phone",
  "items": [
    {
      "source": "sijil",
      "ref": "42",
      "number_label": "T3C-1042",
      "legacy_number": null,
      "full_name": "تجربة اختبار نموذج",
      "tower_name": "العلم 3",
      "tower_code": "ALM03",
      "phone": "07801234567",
      "status": "linked",
      "registered_at": "2026-11-20T09:00:00Z",
      "deleted": false
    },
    {
      "source": "sas",
      "ref": "918",
      "number_label": null,
      "legacy_number": null,
      "full_name": "مشترك SAS تجريبي",
      "tower_name": null,
      "tower_code": "ALM03",
      "phone": "07801234567",
      "status": "expires 2026-12-01",
      "registered_at": "2025-02-01T00:00:00Z",
      "deleted": false
    }
  ],
  "total": 2
}
```

- A deleted request (only for `kind: number`): `{"source":"sijil","ref":"…","number_label":"T3C-…","deleted":true}`
  with every other field null.
- SAS `status` is the expiry date as stored; the page renders «حسب آخر استيراد».

| Error | When |
|---|---|
| `422 search_unclear` «اكتب اسماً (3 أحرف على الأقل) أو هاتفاً أو رقماً» | `q` is none of the kinds |
| `403 identity_search_forbidden` «البحث بالرقم الوطني أو العائلي يحتاج صلاحية المراجعة» | kind `national_id` or `family` without `review` — decided before any query |

## New: `GET /api/admin/subscribers/{source}/{ref}`

`source ∈ sijil | legacy | sas`. `404 not_found` for an unknown record.

```json
{
  "record": {
    "source": "sijil",
    "ref": "42",
    "number_label": "T3C-1042",
    "full_name": "…",
    "phone": "07801234567",
    "username": "ALM03-07801234567",
    "tower_name": "العلم 3",
    "tower_code": "ALM03",
    "registered_at": "…",
    "status": "linked",
    "type": "new",
    "marketer_name": "…",
    "national_id": "199012345678",
    "family_number": "1990A1234567890123",
    "card_fields": {"birth_date": "…"},
    "images": [{"id": "…", "side": "front"}],
    "incomplete": false,
    "deleted": false
  },
  "history": [
    {"kind": "submitted", "at": "…", "by_name": "مسوّق تجريبي"},
    {"kind": "approved", "at": "…", "by_name": null},
    {"kind": "pinned", "at": "…", "by_name": "…", "field": "national_id"},
    {"kind": "linked", "at": "…", "by_name": "…"},
    {"kind": "unlinked", "at": "…", "by_name": "…", "reason": "by_mistake"}
  ],
  "linked": [
    {"reason": "same_phone", "row": {"source": "sas", "ref": "918", "full_name": "…", "status": "…"}}
  ],
  "more_linked": 0
}
```

- For a caller with `link` or `reports` and without `review`: the keys `national_id`, `family_number`,
  `card_fields` and `images` are **absent** from `record` (legacy: also absent; legacy `extra` keeps no identity
  number). `pinned` lines keep `kind`, `at`, `by_name` only.
- Legacy `record` adds `legacy_number`, `status_text`, `counts_in_check`, `extra`, `incomplete`; SAS adds
  `expires_at`, `group_name`, `last_online_at`, `missing_since`, `username_phone`, `no_documents: true`.
- A deleted request: the kept fields only (011) and `deleted: true`; no `linked`, no images.
- Images open through the existing `/api/admin/request-images/{id}` and `/api/admin/legacy-images/{id}` (review
  only, every open logged).

## Web routes

| Path | Who | Page |
|---|---|---|
| `/admin/subscribers` | main admin, `review`, `link`, `reports` | search box and result list (replaces the placeholder) |
| `/admin/subscribers/:source/:ref` | same | the file |
