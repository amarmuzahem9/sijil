# Data Model: Reports and Export (019)

One migration: `0021_exports`.

## `exports` (new)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | also the folder name `EXPORTS_DIR/<id>/` |
| `requester_id` | bigint FK users, not null | only this user may see, ticket or download it |
| `filters` | jsonb not null | `{period, from, to, date_kind, area_id, tower_id, marketer_id, plan_id, status, type}` (ids and codes only) |
| `include_identity` | bool not null | the ticked box (FR-008); true only if allowed when asked (R1) |
| `state` | text not null | `preparing` → `ready` \| `failed`; `ready`/`failed` → `removed` |
| `row_count` | int | set when ready |
| `missing_images` | int | set when ready (identity exports) |
| `error_code` | text | on `failed` only; no row data |
| `ticket_hash` | text | SHA-256 of the current download ticket; cleared when used |
| `ticket_expires_at` | timestamptz | now + 60 s at issue |
| `created_at` | timestamptz not null | |
| `ready_at` | timestamptz | |
| `expires_at` | timestamptz | `ready_at + 24 h` |
| `removed_at` | timestamptz | |

Constraints:
- `exports_state CHECK (state IN ('preparing','ready','failed','removed'))`;
- `CHECK ((state = 'ready') = (ready_at IS NOT NULL AND expires_at IS NOT NULL AND removed_at IS NULL))` (a removed
  row keeps `ready_at`);
- a partial unique index `exports_one_preparing (requester_id) WHERE state = 'preparing'` (one build per admin).

Index: `exports_requester_created (requester_id, created_at DESC)`.

Rows are kept after removal (state `removed`) as a small history for the requester's list; the file is gone. No
subscriber data is stored in the row.

## Files (volume `exports`, api only)

```text
/data/exports/<export id>/
├── requests.xlsx     # the sheet (R9); holds identity columns only if include_identity
└── manifest.json     # [{number, front, back}] stored image file names; identity exports only
```

Removed on expiry or failure (R10). Never in backups.

## `requests` (existing)

New index `requests_submitted_at_idx (submitted_at DESC, id DESC)` for the submission-date filter. No column change.
Read only: no value is written by this feature.

## `image_access_log` (existing)

`image_access_log.purpose`: the check `image_access_log_purpose` widens from `IN ('view','ocr')` to
`IN ('view','ocr','export')` (migration 0021). The downgrade restores the old list, and refuses if `export` rows exist
(access rows are never deleted). One row per card image sent in a download: `user_id` = the requester, `image_id`,
`request_id`, `side`, `purpose = 'export'` (research R6, analysis C1).

## `audit_log` (existing)

New actions (R8), no personal data:

| action | entity_type / entity_id | after |
|---|---|---|
| `requests.exported` | `export` / export id | `filters`, `row_count`, `numbers` (request numbers), `identity`, `missing_images` |
| `export.downloaded` | `export` / export id | `images` (number of card images sent) |
| `commissions.exported` | `commission_month` / `YYYY-MM` | `month` |

## Commission data (existing, 017)

`commission_payments`, `commission_payment_requests`, tiers: read only, through `commission_service.report` and
`detail`.

## State transitions

```text
(POST) ──► preparing ──build ok──► ready ──24 h──► removed
               │                      │
               └──error / restart──► failed ──sweep──► removed
ready: an identity export whose requester lost `review` or `reports` ──download attempt──► removed
```
