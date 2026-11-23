# Data Model: Request Check and Decision at Submission (008)

Migration `0010_requests`. It adds three tables, one sequence and one draft column. Every time is
UTC (Principle X).

## New sequence `request_number_seq`

`START 1001 INCREMENT 1`. Each request takes its number at submission, and a number is never reused
(research R7).

## New table `requests`

| Column | Type | Null | Rule |
|---|---|---|---|
| `id` | bigint identity | no | PK |
| `number` | integer | no | UNIQUE; from `request_number_seq`; shown as `T3C-{number}` |
| `draft_id` | uuid | no | UNIQUE; the submitted draft's id, with no FK (the draft is removed). Used to make submission idempotent (R6) |
| `marketer_id` | bigint FK `users.id` RESTRICT | no | |
| `type` | text | no | CHECK `IN ('new','additional','return')`; 008 writes `new`, `additional` |
| `status` | text | no | CHECK `IN ('pending_review','approved','rejected','linked')`; 008 writes `approved`, `pending_review` |
| `first_name` … `mother_surname` | text | the 7 required: no; the 2 optional: yes | the nine name fields, copied |
| `full_name` | text | no | |
| `no_surname` | boolean | no | CHECK `NOT no_surname OR surname IS NULL` |
| `national_id` | text | no | the normalized 12 digits; CHECK `~ '^[0-9]{12}$'` |
| `national_id_input` | text | no | as written on the draft |
| `family_number` | text | no | as written |
| `family_key` | text | no | R3 key; CHECK `~ '^[A-Z0-9]+$'` |
| `birth_date`, `issue_date`, `expiry_date` | date | no | |
| `birth_place`, `issuing_authority` | text | no | |
| `card_fields` | jsonb | no | copied from the draft (006 shape) |
| `national_id_check` | jsonb | yes | copied |
| `card_readings` | jsonb | no | `{front: {state, reason, raw, result, finished_at} \| null, back: …}`; never returned to any page or logged |
| `location_lat`, `location_lng` | float | no | |
| `location_source` | text | no | |
| `location_accuracy_m` | integer | yes | |
| `address`, `landmark` | text | no | |
| `area_id`, `tower_id`, `plan_id` | bigint FK, RESTRICT | no | a used catalog item cannot be deleted (also through the usage registry, R9) |
| `area_name`, `tower_code`, `plan_name` | text | no | copies fixed at submission |
| `trial_price`, `second_price` | integer | no | copies fixed at submission |
| `phone` | text | no | the verified, normalized phone; CHECK `~ '^07[0-9]{9}$'` |
| `username` | text | no | `{tower_code}-{phone}`; not unique (R7) |
| `otp_verified_at` | timestamptz | no | copied from the draft (Principle IV) |
| `submitted_at` | timestamptz | no | |
| `approved_at` | timestamptz | yes | set when approved. 008 sets it on an automatic approval |
| `approved_by` | bigint FK `users.id` | yes | null with `approved_at` set = automatic approval |
| `created_at`, `updated_at` | timestamptz | no | |

Indexes:
- `requests_phone_idx (phone)`;
- `requests_national_id_idx (national_id)`;
- `requests_family_key_idx (family_key)`;
- `requests_marketer_submitted_idx (marketer_id, submitted_at DESC)`.

The match lookups add `status IN ('pending_review','approved','linked')`.

Checks:
- `no_surname` or `surname IS NOT NULL` (the surname is required unless «لا يوجد لقب على البطاقة»);
- `status = 'approved'` implies `approved_at IS NOT NULL`;
- `status = 'pending_review'` implies `approved_at IS NULL`.

Requests are never deleted (Principle III). The model has no delete path.

## New table `request_reasons`

One row per §6.1 reason that applies (FR-003, FR-014).

| Column | Type | Null | Rule |
|---|---|---|---|
| `id` | bigint identity | no | PK |
| `request_id` | bigint FK `requests.id` CASCADE | no | |
| `reason` | text | no | CHECK `IN ('family_exists','numbers_edited','return')`; `return` comes in 009 |
| `matched_source` | text | yes | `sijil` (later `legacy`, `sas`); set for `family_exists` |
| `matched_ref` | text | yes | the matched record's id in its source |
| `details` | jsonb | no, default `{}` | `numbers_edited`: `{"fields": ["national_id" \| "family_number", …]}` |
| `created_at` | timestamptz | no | |

UNIQUE NULLS NOT DISTINCT `(request_id, reason, matched_source, matched_ref)`, so a `numbers_edited` row (no match) cannot repeat. With several family matches there is one
row per match.

## New table `request_images`

| Column | Type | Null | Rule |
|---|---|---|---|
| `id` | uuid | no | PK; the draft image's id, kept |
| `request_id` | bigint FK `requests.id` RESTRICT | no | |
| `side` | text | no | CHECK `IN ('front','back')`; UNIQUE `(request_id, side)` |
| `file_name` | text | no | the same file in `UPLOADS_DIR` (not moved) |
| `size_bytes`, `width`, `height` | integer | no | |
| `uploaded_by` | bigint FK `users.id` | no | |
| `created_at` | timestamptz | no | the original upload time |

`draft_service.referenced_file_names` includes these file names (R1).

## Change to `drafts`

| Column | Type | Null | Rule |
|---|---|---|---|
| `additional_confirmed_key` | text | yes | The family key the marketer confirmed with «طلب اشتراك إضافي» (R12). It is valid only while it equals `family_key(family_number)` and a family match exists |

PATCH accepts `additional_confirmed: bool`:
- `true` is accepted only while a family match exists, else 422 `no_family_match`;
- `false` clears the key.

## Derived: `DraftOut.checks`

```json
{"phone_used": false, "national_id_exists": false, "family_exists": true, "additional_confirmed": false}
```

New missing items:
- `national_id_exists`;
- `family_exists_unconfirmed`;
- `phone_used`.

They are inserted after `national_id_unconfirmed`, `family_number` and `phone` in `MISSING_ORDER` (research R5).

## Request lifecycle (008 part of §7.2)

```text
draft ──submit, no reason──────────────► request approved      (approved_at = submitted_at, approved_by null)
draft ──submit, family and/or edited───► request pending_review (+ request_reasons)
draft ──submit, phone used / NID found──► refused; the draft stays; audit request.submit_refused
pending_review ──► approved | rejected   (010)
approved ──► linked ──► approved         (012)
```

Submitting deletes the draft row. Its `draft_images` and `card_readings` rows go with it, and their
data now lives on the request. `otp_challenges.request_id` becomes null, and the rows still count
toward the hourly limit.

## Audit actions

| Action | entity | after |
|---|---|---|
| `request.submitted` | `request` / number | `{number, type, status, reasons, tower_code, plan_name}` |
| `request.submit_refused` | `draft` / id | `{reason: "phone_used" \| "national_id_exists"}` |

No national ID, family number, phone, names or images (R13).
