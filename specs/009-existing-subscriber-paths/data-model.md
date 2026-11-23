# Data Model: Existing Subscriber Paths (009)

Migration `0011_existing_subscriber_paths`. It only adds things; no data is moved.

## drafts (changed)

| Column | Type | Rule |
|---|---|---|
| `return_key` | text, null | `identity:{national_id}:{family_key}` or `phone:{phone}` ([research R3](./research.md#r3-storing-the-choice-a-key-like-008s-confirmation)). The choice counts only while the draft's current values give the same key and the return target is not empty. NULL means no return chosen. Cannot be set together with `additional_confirmed_key` (one is cleared when the other is set). |

## request_reasons (changed)

- The check constraint `request_reasons_reason` becomes
  `reason IN ('family_exists','numbers_edited','return','numbers_conflict')`.
- `return` rows: one per record in the return target, with `matched_source` and `matched_ref`, and
  `details = {"basis": "identity"|"phone"}`.
- `numbers_conflict` rows: one per conflicting record, with `matched_source` and `matched_ref`.

## requests (no new column)

- `type = 'return'` is already allowed by 008's check constraint.
- `username` for a return: the newest target record's username, else `{tower_code}-{phone}`
  ([R7](./research.md#r7-submission-changes)).

## app_settings (new key)

| Key | Value | Rule |
|---|---|---|
| `admin_whatsapp` | JSON string `"07XXXXXXXXX"` or absent | Normalized by §8.1. Empty input deletes the row. Changed only with `settings`. Audited `app_setting.updated` with before and after values. |

## In memory (not stored)

### MatchRecord

`source`, `ref_id`, `phone`, `national_id`, `family`, `pending` (booleans). One per matching record.

### Matches views

[research R1](./research.md#r1-matches-per-record-not-per-key): `phone`, `same_person`,
`id_conflict`, `family`, and the return target `T` (R2).

### Decision

008 fields plus:
- `type` can be `return`;
- `refusal` can be `return_pending`;
- `reasons` can hold `return` and `numbers_conflict`;
- `result` can be `pending_approval`.

### DraftChecksOut

| Field | Meaning |
|---|---|
| `phone_used` | phone held by a record; with a valid return, only by a record outside `T` |
| `national_id_exists` | `same_person` not empty |
| `id_conflict` | `id_conflict` not empty |
| `family_exists` | family-only records exist |
| `additional_confirmed` | as in 008 |
| `return_available` | `T` not empty |
| `return_basis` | `identity`, `phone` or null |
| `return_chosen` | `return_key` is valid |
| `return_pending` | chosen and a record in `T` is pending |

### Missing items

| Item | Shown when |
|---|---|
| `national_id_exists` | `same_person` and no return chosen |
| `phone_used` | as in the checks above |
| `family_exists_unconfirmed` | family records exist, no return chosen, not confirmed |
| `return_pending` (new) | as in the checks above |

## State transitions

Unchanged (§7.2). A return or conflict request is created with `pending_review`. Accept and reject
are added in 010.
