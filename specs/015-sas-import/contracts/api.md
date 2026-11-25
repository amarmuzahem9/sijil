# API Contract: Import of the SAS Subscribers (015)

All routes are under `/api`, with Bearer auth. Errors use the existing `{"code": "...", ...}` shape, and the web maps
codes to Arabic. No response or log line ever carries a `ct_password` value. No marketer route changes shape.

## Import (main admin or `reports`; anyone else → 403 `forbidden`)

### `POST /api/admin/imports/sas/previews`

Multipart: `file` (`.xlsx` or `.csv`, ≤ 15 MB). Cancels the caller's open SAS preview. Built synchronously.

- `201` → `SasPreview`.
- `422 import_file_unreadable`; `422 import_columns_missing` `{ "columns": ["username"] }`;
  `422 import_too_many_rows` (> 50 000); `413 import_file_too_large`.

### `GET /api/admin/imports/sas/previews/{id}`

Only the caller's own preview. Another admin's preview, or an expired one, → `404 preview_not_found`.

`SasPreview`:
```json
{
  "id": "uuid", "file_name": "…", "expires_at": "…",
  "counts": { "rows": 12000, "new": 140, "update": 310, "unchanged": 11530, "missing_from_file": 25,
              "flagged": 12, "waiting_choice": 12, "same_username_in_sijil": 220, "no_valid_phone": 41,
              "username_no_phone": 3, "date_unreadable": 2, "phone_dup_file": 18, "phone_in_legacy": 4 },
  "prefixes": [ { "prefix": "ZZQ07", "rows": 35, "tower_id": null, "from_previous": false, "chosen": false },
                { "prefix": "OLD-1", "rows": 4, "tower_id": 12, "from_previous": true, "chosen": true } ],
  "waiting_prefixes": 1,
  "flagged": [
    { "index": 418, "sas_id": "5521", "username": "…", "full_name": "…", "phone": "07…|null",
      "username_phone": "07…|null", "kind": "new|update",
      "flags": [ { "code": "username_dup_file", "rows": [977] },
                 { "code": "phone_in_sijil", "requests": ["T3C-1004"] } ],
      "allowed": ["import", "skip"], "choice": null }
  ]
}
```
Only flagged rows are listed. Ready rows are counted. `prefixes` lists the prefixes that need a mapping (no rule
match), pre-filled from `sas_tower_mappings` when saved before. `chosen` is true when a tower or «بلا برج» is set.

### `PUT /api/admin/imports/sas/previews/{id}/choices`

Body (partial updates allowed):
```json
{ "choices": [ { "index": 418, "choice": "import|skip" } ],
  "prefixes": [ { "prefix": "ZZQ07", "tower_id": 7 }, { "prefix": "OLD-1", "tower_id": null } ] }
```
`tower_id: null` means «بلا برج». The tower must exist (active or stopped), otherwise `422 tower_not_found`.
«تخطي للكل» is the client sending `skip` for every row of the group.

- `200` → `SasPreview`.
- `422 choice_not_allowed`: for example `import` on `username_missing`, or two `import` on one repeated username.

### `POST /api/admin/imports/sas/previews/{id}/confirm`

Takes the shared import lock (one SAS or legacy confirmation at a time).

- `201` → `SasImportSummary`:
  ```json
  { "import_id": 3, "rows": 12000, "added": 138, "updated": 310, "unchanged": 11530, "skipped": 22,
    "missing_marked": 25, "missing_cleared": 6, "without_phone": 41, "prefixes_mapped": 2,
    "skipped_rows": [ { "index": 418, "sas_id": "5521" } ] }
  ```
  No usernames, phones or names.
- `409 preview_choices_missing` `{ "indexes": [418], "prefixes": ["ZZQ07"] }`.
- `409 preview_changed`: re-validation found a row that now needs a choice, or a new unknown prefix. The body
  carries the updated `SasPreview` in `preview`, and unchanged rows keep their choices.
- `404 preview_not_found`.

### `DELETE /api/admin/imports/sas/previews/{id}`

Cancels the preview. Returns `204`.

## Review file (changed)

`GET /api/admin/requests/{id}`: `reasons[].record` (`LinkedRecordOut`) for `source = "sas"`:

```json
{ "source": "sas", "ref": "981", "available": true,
  "username": "ALM03-07801234567", "full_name": "…", "phone": "07…", "username_phone": null,
  "tower_code": "ALM03", "tower_name": "العلم 3", "registered_at": "<SAS created_at>",
  "expiry": "2026-12-01", "expiry_as_of": "2026-11-25", "last_online": "…", "group_name": "PLUS",
  "missing_from_file": null, "image_ids": [], "legacy_number": null }
```
The new optional fields (`expiry_as_of`, `last_online`, `group_name`, `username_phone`, `missing_from_file`) are
null or absent for other sources. The record never carries a national ID, family number, notes or parent_name.

## Unchanged (tested to stay so)

These routes keep their shapes, and a SAS match shows only as the existing case 1 outcome:
- marketer routes: draft checks, OTP precheck, submit, requests, home, notifications;
- «بانتظار الربط» and «المربوطة مؤخراً» (FR-023).
Settings: deleting a tower, or editing its code, while a SAS subscriber or mapping uses it → the existing
`item_in_use` refusal.
