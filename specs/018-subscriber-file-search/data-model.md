# Data Model: 018 Subscriber File and Search

**No migration.** The feature reads existing tables only (Q3: read-only). New code builds views of them.

## Read sources (existing)

| Source | Table | Keys used | Registration time |
|---|---|---|---|
| `sijil` | `requests` (+ `request_number_pins`, `request_links`, `request_images`) | `phone`, `national_id`, `family_key`, `username`, `number`, `full_name` | `submitted_at` |
| `legacy` | `legacy_subscribers` (+ `legacy_images`) | `phone`, `family_key`, `legacy_number`, `full_name` | `form_submitted_at`, else `created_at` |
| `sas` | `sas_subscribers` | `phone`, `username_phone`, `username_key`, `full_name` | `sas_created_at`, else `created_at` |

Existing indexes cover the exact keys (`requests_phone_idx`, `requests_national_id_idx`, `requests_family_key_idx`,
`sas_subscribers_phone`, SAS username key, legacy phone and family key). Name search folds on read (research R3).

## Derived: search term

| Kind | From | Sources | Needs `review` |
|---|---|---|---|
| `number` | request number | `sijil` (deleted included, «سجل محذوف») | no |
| `legacy_number` | «T3C-001»… | `legacy` | no |
| `national_id` | 12 digits | `sijil` | **yes** |
| `phone` | §8.1 | all three (SAS: both phones) | no |
| `family` | §6.2 key | `sijil`, `legacy` | **yes** |
| `username` | `PREFIX-07…`, upper | `sijil`, `sas` | no |
| `name` | folded, ≥ 3 letters | all three | no |

## Derived: result row

`source`, `ref`, `full_name`, `tower_name`/`tower_code` (SAS: mapped tower or prefix), `phone`, `status`
(request status | legacy `status_text` | SAS «حسب آخر استيراد» expiry), `registered_at`, `deleted` (sijil only),
`number_label` / `legacy_number`. Never identity numbers.

## Derived: file

- **record**: per source, the display fields of 010/014/015 (`LinkedRecord`-like), plus for `sijil` the request
  fields of the review file. Identity fields (`national_id`, `family_number`, card fields and readings, image ids)
  only for the main admin and `review` (research R7).
- **linked**: up to 50 `{source, ref, reason ∈ same_person | same_phone | same_family, row}`, strongest reason per
  record; `more: int`.
- **history** (sijil): ordered events `{kind ∈ submitted | approved | rejected | pinned | linked | unlinked |
  deleted, at, by_name, reason?, field?}`; `pinned` never carries a value.
- **flags**: `incomplete` (legacy missing an image), `no_documents` (SAS), `missing_from_file` (SAS), `deleted`.
