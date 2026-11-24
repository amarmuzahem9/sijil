# Data Model: Import of the Legacy Subscribers (014)

Migration `0017_legacy_import`. All timestamps `timestamptz`, stored in UTC (Principle X). Nothing here is ever
physically deleted except preview rows (temporary, R9).

## legacy_imports

One confirmed import (research R10, R11).

| Column | Type | Rules |
|---|---|---|
| id | bigint identity PK | |
| created_by | bigint FK users | the admin who confirmed |
| created_at | timestamptz | default now |
| file_name | text | as uploaded, at most 200 chars |
| rows_total | int | rows in the file |
| imported | int | |
| skipped | int | chosen «تخطي» |
| already_imported | int | legacy number already in the table (R6) |
| not_counted | int | imported with `counts_in_check = false` |
| incomplete | int | imported with a missing image |
| corrected | int | family numbers corrected by the admin |

## legacy_subscribers

One person from the old Google Form (spec › Key Entities; FR-006). No national ID, username, tower or marketer.

| Column | Type | Rules |
|---|---|---|
| id | bigint identity PK | |
| import_id | bigint FK legacy_imports | |
| legacy_number | text, UNIQUE | `^T3C-\d{3}$` (check constraint) |
| form_submitted_at | timestamptz NULL | the «طابع زمني», Baghdad time → UTC |
| first_name, second_name, third_name | text NULL | trimmed, spaces collapsed, as written |
| full_name | text NOT NULL | first + second + third, empty parts skipped |
| family_number_file | text NULL | the file value as written |
| family_number | text NULL | value in use: the file value, or the admin's correction |
| family_key | text NULL | §6.2 key of `family_number`; indexed |
| phone | text NULL | §8.1 normalized (`^07\d{9}$` check); NULL when invalid or empty; indexed |
| phone_file | text NULL | the file value as written (the admin compares it if the phone was invalid) |
| status_text | text NULL | «الحالة» as written |
| counts_in_check | boolean NOT NULL | `status_text` trimmed not in («ملغي», «مرفوض») (R3) |
| extra | jsonb NOT NULL default `{}` | `mother_name`, `mother_father_name`, `birth_date`, `email_1`, `email_2` — text |
| incomplete | boolean NOT NULL | true when the front or the back image is missing |
| created_at | timestamptz | |

Indexes: `(phone) WHERE counts_in_check`, `(family_key) WHERE counts_in_check`.
Read-only after insert in this feature (no update route).

## legacy_images

| Column | Type | Rules |
|---|---|---|
| id | uuid PK | |
| legacy_subscriber_id | bigint FK legacy_subscribers | |
| side | text | `front` \| `back`; UNIQUE (legacy_subscriber_id, side) |
| file_name | text | `<uuid hex>.jpg` in the uploads volume (image_store) |
| size_bytes, width, height | int | after re-encoding (≤ 1 600 px, JPEG q80, R7) |
| created_at | timestamptz | |

A missing or failed image has no row; the fetch outcome is kept in the audit counts and, per row, in the summary
returned at confirmation (not stored, it holds no lasting value beyond «غير مكتمل»).

## legacy_import_previews (temporary)

| Column | Type | Rules |
|---|---|---|
| id | uuid PK | |
| created_by | bigint FK users | one open preview per admin (a new upload cancels the old one) |
| created_at, expires_at | timestamptz | expires_at = created_at + 1 h |
| status | text | `fetching` → `ready`, or `failed` (restart, unreadable) |
| file_name | text | |
| images_total, images_done | int | progress for «جارٍ سحب الصور» |
| rows | jsonb | list of `PreviewRow` (below) |

`PreviewRow` (JSON, never logged): `index` (row number in the file, from 2), `legacy_number`, `names`, `full_name`,
`family_number_file`, `family_key`, `phone_file`, `phone`, `status_text`, `counts_in_check`, `extra`,
`form_submitted_at`, `images` (`front`/`back`: `{outcome, staged_file?, width?, height?, size_bytes?}` with outcome
`ok` | `missing` | `not_shared` | `not_found` | `too_large` | `not_image` | `timeout` | `network`), `flags` (R6 codes,
`in_sijil` with request numbers), `choice` (`import` | `skip` | `correct` | null), `corrected_family_number`.

Deleted (with its staged files) on successful confirmation, on expiry, or when replaced.

## image_access_log (changed)

Add `legacy_subscriber_id bigint NULL` (plain value, not FK, like `request_id`). Set when a review admin opens a legacy
image (R13).

## Relations to existing data

- `request_reasons.matched_source = 'legacy'`, `matched_ref = legacy_subscribers.id` (text) — written by the
  existing submit and re-check code when the `legacy` source matches. No schema change.
- `draft_service.referenced_file_names` adds `legacy_images.file_name` and every `staged_file` in open previews.

## Rules (tested)

- `counts_in_check` false ⇒ the row never appears in `find_matches`.
- The `legacy` source never sets `national_id` or `pending` on a `MatchRecord`.
- `legacy_number` unique; a re-upload never updates an existing row (FR-020).
- A failed confirmation inserts nothing into `legacy_imports`, `legacy_subscribers`, `legacy_images`.
