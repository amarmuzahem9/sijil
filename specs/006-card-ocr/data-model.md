# Data Model: Automatic National Card Reading (OCR)

Migration `0007_card_reading`. It builds on 005's `drafts` and `draft_images`
([005 data-model](../005-subscriber-form/data-model.md)). All timestamps are UTC (Principle X).

## Changes to `drafts`

| Column | Type | Null | Rule |
|---|---|---|---|
| `card_fields` | jsonb | no, default `{}` | Provenance of the eight card fields (R8). Keys: `first_name`, `father_name`, `grandfather_name`, `surname`, `mother_first_name`, `mother_second_name`, `national_id`, `family_number`. Value: `{source: "card"\|"edited", original: text\|null, confidence: float\|null, from: "front"\|"back"\|"mrz"\|null}`. Validated by a Pydantic model before writing. |
| `no_surname` | boolean | no, default false | «لا يوجد لقب على البطاقة» (FR-017, R9). CHECK: `NOT no_surname OR surname IS NULL`. |
| `national_id_check` | jsonb | yes | Set only while a verified MRZ exists (R7): `{mrz: "12 digits", confirmed_value: text\|null}`. Null when there is no verified MRZ. |

The derived states are computed, not stored:
- **National-ID mismatch**: `national_id_check` exists and `national_id ≠ mrz`.
- **Mismatch resolved**: the mismatch exists and `confirmed_value = national_id`.

### Rules on save (PATCH, `draft_service.apply_changes`)

- **Marking edits**: Changing any of the eight card fields sets `card_fields[field].source =
  "edited"`. The existing `original`, `confidence` and `from` are kept; a missing entry gets
  `original: null`.
- **`no_surname: true`**: sets `surname = null` and marks the surname `edited`.
- **A non-empty `surname`**: sets `no_surname = false`.
- **Confirming the national ID**: `national_id_confirmed: true` is accepted only together with,
  or after, a mismatch. It stores `confirmed_value = national_id`. Any change of `national_id`
  sets `confirmed_value = null`.
- `full_name` is unchanged: it is the first five names, empty parts skipped.

## New table `card_readings`

One row per draft and side: the latest reading of that side's current image.

| Column | Type | Null | Rule |
|---|---|---|---|
| `id` | bigint identity | no | PK |
| `draft_id` | uuid | no | FK `drafts.id` ON DELETE CASCADE |
| `side` | text | no | `front` \| `back`; UNIQUE (`draft_id`, `side`) |
| `image_file_name` | text | no | The `draft_images.file_name` this reading belongs to; a result for another file name is dropped (R5) |
| `state` | text | no | `pending` \| `running` \| `done` \| `reshoot` \| `failed` |
| `reason` | text | yes | Required for `reshoot` (`no_card`, `wrong_side`, `not_unified`, `multiple`) and `failed` (`timeout`, `unavailable`, `error`); null otherwise |
| `raw` | jsonb | yes | The reader's raw result for this side (R4), as received; set when the reader answered |
| `result` | jsonb | yes | The evaluated side (R6), set for `done`. Front: `{fields: {label: {text, confidence}}, surname_empty: bool}`. Back: `{family_number: {text, normalized, confidence}, mrz: {verified: bool, national_id, document_number, checks: {number, birth, expiry, composite}}}` |
| `queued_by_client` | uuid | yes | The upload's `X-Client-Id`, used as `last_client_id` when the result is applied (R8) |
| `started_at` | timestamptz | yes | When the job sent it to the reader |
| `finished_at` | timestamptz | yes | When it reached `done`, `reshoot` or `failed` |
| `duration_ms` | integer | yes | Reader time, for monitoring |
| `created_at` / `updated_at` | timestamptz | no | |

CHECK constraints:
- `state` is one of the five values;
- `reason` is set when `state` is `reshoot` or `failed`;
- `reason` is null otherwise.

### State transitions

```text
(image uploaded)      → pending              (upload transaction, R5)
pending               → running              (job starts; both sides present)
running               → done | reshoot | failed
running (> 60 s)      → failed/timeout       (startup sweep or lazy check)
failed                → pending              (POST …/card-reading/retry)
any                   → pending              (that side's image replaced; raw/result cleared)
draft deleted         → (row removed by CASCADE)
```

A reading does not start while the other side has no image. The row stays `pending` until the
second upload queues the job (FR-001).

### Applying a `done` pair to the draft (one locked transaction)

Runs when a side reaches `done` and the other side is `done` or `reshoot`/`failed`. Fields of
a successful side are applied even when the other side failed (spec edge case).

| Form field | From | Validation before writing |
|---|---|---|
| `first_name` | front `name` | §5.1 name rule (`clean_arabic_name`) |
| `father_name` | front `dad` | name rule |
| `grandfather_name` | front `gf` | name rule |
| `surname` | front `last` | name rule; skipped while `no_surname` is true; empty text → `surname_empty` hint |
| `mother_first_name` | front `mom` | name rule |
| `mother_second_name` | front `gm` | name rule |
| `national_id` | front `id`, else the verified MRZ `optional1` | `normalize_national_id` → 12 digits |
| `family_number` | back `nu_f` | R6 step 6 normalization and pattern |

Each field is written only when `card_fields[field]` is absent or `source = "card"` (FR-007).
Its `original`/`confidence`/`from` are always updated to the new reading. The apply step then
does three more things:
1. It recomputes `full_name` and re-evaluates `national_id_check` (R7).
2. It increments `version`.
3. It sets `last_client_id = queued_by_client`.

## Validation (`draft_validation.missing`)

Added or changed items, in page order:
- **`surname`**: required unless `no_surname` (the label is unchanged).
- **`national_id_unconfirmed`**: the national ID differs from the verified MRZ and is not
  confirmed. Its label is «تأكد من الرقم الوطني».

The shared fixture `draft_validation_cases.json` gains these cases, and pytest and vitest both
read it.

## Constants (`api/app/core/card_reading.py`, mirrored in `web/src/lib/cardReading.ts` where needed)

| Name | Value | Source |
|---|---|---|
| `SECOND_PASS_MIN` | 0.50 | upstream threshold for a card candidate |
| `SECOND_DOC_HIGH` | 0.90 | R6.4, above step 0's phantom (0.876) |
| `DUPLICATE_IOU` | 0.5 | R6.3 |
| `OTHER_DOC_MIN` | 0.50 | R6.1 |
| `READING_LIMIT_S` | 60 | FR-014 |
| `READER_HTTP_TIMEOUT_S` | 45 | R5 |
| `READING_POLL_MS` | 2000 | R5 (web) |
| `FAMILY_NUMBER_RE` | `^\d{4}[A-Z][0-9A-Z]{13}$` | FR-006 |

## What is never stored

- No copy of a card image is kept outside `uploads`. The reader keeps nothing.
- No card text, number or MRZ appears in `audit_log` or in application logs (FR-019).
- Reading a card is not an audited action: it is not a decision. Deleting a draft (already
  audited in 005) removes its readings through CASCADE.
