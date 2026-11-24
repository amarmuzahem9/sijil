# API Contract: Import of the Legacy Subscribers (014)

All routes under `/api`, Bearer auth. Errors use the existing `{"code": "...", ...}` shape; the web maps codes to
Arabic. No response or log line ever carries card images' bytes outside the image route, and no marketer route
changes shape.

## Import (main admin or `reports`; anyone else → 403 `forbidden`)

### `POST /api/admin/imports/legacy/previews`

Multipart: `file` (`.xlsx` or `.csv`, ≤ 5 MB). Cancels the caller's open preview.

- `201` → `Preview` (status `fetching`).
- `422 import_file_unreadable` — not a readable sheet or CSV.
- `422 import_columns_missing` `{ "columns": ["الرقم العائلي", …] }`.
- `422 import_too_many_rows` (> 2 000), `413 import_file_too_large`.

### `GET /api/admin/imports/legacy/previews/{id}`

The caller's own preview only (another's or an expired one → 404 `preview_not_found`).

`Preview`:
```json
{
  "id": "uuid", "status": "fetching|ready|failed", "file_name": "…", "expires_at": "…",
  "images_total": 218, "images_done": 140,
  "counts": { "rows": 109, "ready": 90, "flagged": 19, "already_imported": 0,
              "not_counted": 3, "waiting_choice": 19 },
  "status_values": [ { "value": "تم", "rows": 100, "counts_in_check": true },
                     { "value": "ملغي", "rows": 3, "counts_in_check": false } ],
  "flagged": [
    { "index": 14, "legacy_number": "T3C-012", "full_name": "…", "phone_file": "…", "phone": "07…|null",
      "family_number_file": "…", "status_text": "…", "counts_in_check": true,
      "flags": [ { "code": "family_dup_file", "rows": [27] },
                 { "code": "in_sijil", "requests": ["T3C-1004"] },
                 { "code": "image_failed", "side": "back", "outcome": "not_shared" } ],
      "allowed": ["import", "skip", "correct"], "choice": null, "corrected_family_number": null }
  ]
}
```
`flagged` is present only when `status = ready`. Ready rows are counted, not listed.

### `PUT /api/admin/imports/legacy/previews/{id}/choices`

Body: `{ "choices": [ { "index": 14, "choice": "import|skip|correct", "family_number": "…" } ] }` (partial updates
allowed). `family_number` required with `correct` (trimmed, 1–40 chars); the new value is re-checked for duplicates
and length, and its flags are returned.

- `200` → `Preview`.
- `409 preview_not_ready`, `422 choice_not_allowed` (e.g. `import` on `legacy_number_missing`, two `import` on one
  repeated legacy number).

### `POST /api/admin/imports/legacy/previews/{id}/confirm`

- `201` → `ImportSummary`:
  ```json
  { "import_id": 1, "rows": 109, "imported": 104, "skipped": 5, "already_imported": 0,
    "not_counted": 3, "incomplete": 7, "corrected": 2,
    "skipped_numbers": ["T3C-040", …], "incomplete_numbers": ["T3C-007", …] }
  ```
  No family numbers or phones.
- `409 preview_choices_missing` `{ "indexes": [14, 27] }`.
- `409 preview_changed` — re-validation found new flags; body is the updated `Preview`.
- `409 preview_not_ready`, `404 preview_not_found`.

### `DELETE /api/admin/imports/legacy/previews/{id}`

Cancels; `204`. Removes staged files.

## Review file (changed)

`GET /api/admin/requests/{id}` — `reasons[].record` (`LinkedRecordOut`) for `source = "legacy"`:

```json
{ "source": "legacy", "ref": "42", "available": true,
  "legacy_number": "T3C-042", "full_name": "…", "phone": "07…", "registered_at": "<form timestamp>",
  "status": "<«الحالة» as written>", "incomplete": false,
  "extra": { "mother_name": "…", "mother_father_name": "…", "birth_date": "…" },
  "image_ids": ["uuid", "uuid"], "username": null, "tower_code": null }
```
New optional fields (`legacy_number`, `incomplete`, `extra`) are null/absent for other sources. No family number.

### `GET /api/admin/legacy-images/{image_id}`

Review admins (main admin or `review`) only; everyone else, unknown id, missing file → `404 image_not_found`.
`200 image/jpeg`, `Cache-Control: no-store`. Writes `image_access_log` (`legacy_subscriber_id`, side, `view`).

## Unchanged (tested to stay so)

Marketer routes (drafts checks, submit, requests, home, notifications) keep their shapes; a legacy match surfaces
only as the existing case 1 / case 3 outcomes. `GET /api/admin/requests/by-number/T3C-005` → 404.
