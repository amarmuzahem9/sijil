# Data Model: Import of the SAS Subscribers (015)

Migration `0018_sas_import`. All timestamps are `timestamptz`, stored in UTC (Principle X). Nothing here is ever
physically deleted except preview rows, which are temporary (research R12). No column ever holds a `ct_password`
value (R3).

## sas_imports

One confirmed import (R10).

| Column | Type | Rules |
|---|---|---|
| id | bigint identity PK | |
| created_by | bigint FK users | the admin who confirmed |
| created_at | timestamptz | default now; this is the «حسب آخر استيراد» date |
| file_name | text | as uploaded, at most 200 chars |
| rows_total, added, updated, unchanged, skipped | int | |
| missing_marked, missing_cleared | int | rows that got / lost «غير موجود في آخر ملف» |
| without_phone | int | imported rows with neither phone |
| prefixes_mapped | int | mappings saved or changed by this import |

## sas_subscribers

One SAS username (spec › Key Entities; FR-008). No national ID, family number, images or marketer.

| Column | Type | Rules |
|---|---|---|
| id | bigint identity PK | |
| username | text NOT NULL | as written (trimmed) |
| username_key | text NOT NULL UNIQUE | upper-case, Latin digits (R4) |
| sas_id | text NULL | the `id` column as written |
| first_name, last_name | text NULL | trimmed, spaces collapsed, as written |
| full_name | text NOT NULL | first + last, empty parts skipped (may be empty string) |
| phone | text NULL | phone column per §8.1 (`^07\d{9}$` check); indexed |
| phone_file | text NULL | phone column as written |
| username_phone | text NULL | phone at the end of the username per §8.1 (`^07\d{9}$` check); indexed |
| tower_prefix | text NULL | upper-cased prefix (R4) |
| tower_id | bigint FK towers NULL, ON DELETE RESTRICT | rule or mapping; NULL = «بلا برج» |
| expires_at, sas_created_at, last_online_at | timestamptz NULL | R6 |
| group_name, parent_name, notes | text NULL | as written; notes and parent_name not shown in 015 |
| first_import_id, last_import_id | bigint FK sas_imports | last = the last import that added or updated it |
| missing_since | timestamptz NULL | set when a confirmed file lacks the username; cleared when it returns |
| missing_import_id | bigint FK sas_imports NULL | the import that first missed it |
| created_at, updated_at | timestamptz | |

All rows count in the check (missing rows too, FR-022). Updated only by a confirmed re-import, never by a route.

## sas_subscriber_changes (append-only)

| Column | Type | Rules |
|---|---|---|
| id | bigint identity PK | |
| import_id | bigint FK sas_imports | |
| sas_subscriber_id | bigint FK sas_subscribers | |
| before, after | jsonb | changed fields only (names of R7's compared fields) |
| created_at | timestamptz | |

Never updated or deleted. This is the before/after behind the audit line (constitution III, R10).

## sas_tower_mappings

| Column | Type | Rules |
|---|---|---|
| prefix | text PK | upper-cased prefix with no tower by the rule |
| tower_id | bigint FK towers NULL, ON DELETE RESTRICT | NULL = «بلا برج» |
| set_by | bigint FK users | |
| set_at | timestamptz | |
| import_id | bigint FK sas_imports | the import that saved the current value |

## sas_import_previews (temporary)

| Column | Type | Rules |
|---|---|---|
| id | uuid PK | |
| created_by | bigint FK users | one open preview per admin |
| created_at, expires_at | timestamptz | expires_at = created_at + 1 h |
| file_name | text | |
| rows | jsonb | list of `SasPreviewRow` |
| prefixes | jsonb | list of `{prefix, rows, tower_id, from_previous, chosen}` |
| missing_ids | jsonb | stored subscriber ids absent from the file |

`SasPreviewRow` (JSON, never logged): `index` (file row number, from 2), `sas_id`, `username`, `username_key`,
`first_name`, `last_name`, `full_name`, `phone_file`, `phone`, `username_phone`, `prefix`, `tower_id`,
`expires_at`, `sas_created_at`, `last_online_at`, `group_name`, `parent_name`, `notes`, `date_unreadable`, `kind`
(`new` | `update` | `unchanged`), `stored_id`, `changed` (field names), `flags` (R9 codes, with `rows` or
`requests`), `info` (informational codes), `allowed`, `choice` (`import` | `skip` | null). There is no `ct_password`
key, and it cannot appear (R3).

The preview is deleted on successful confirmation, on expiry, or when replaced.

## Relations to existing data

- `request_reasons.matched_source = 'sas'`, `matched_ref = sas_subscribers.id` (text). The existing submit and
  re-check code writes it when the `sas` source matches. No schema change.
- `requests` is never written by this feature (FR-016).
- The tower usage check (004 registry) counts `sas_subscribers.tower_id` and `sas_tower_mappings.tower_id` (R15).

## Rules (tested)

- No `sas_*` table, preview, audit row, API response or log line ever contains a `ct_password` value.
- The `sas` source matches on `phone` or `username_phone`. It never sets `national_id`, `family` or `pending`, and
  it matches rows with `missing_since` set.
- `username_key` is unique. A re-import updates by key, writes one change row per updated subscriber, and leaves
  unchanged rows untouched (`updated_at` unchanged).
- `missing_since` is set once (the first import that misses the row) and cleared when the row returns.
- A failed or refused confirmation changes no `sas_*` row (SC-007).
- A confirmation never changes any `requests`, `request_links` or `notifications` row.
