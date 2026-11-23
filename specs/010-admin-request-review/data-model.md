# Data Model: Admin Review of Pending Requests (010)

Migration `0013_admin_review`. Every time is UTC (Principle X). Nothing is deleted.

## requests (changed)

| Column | Type | Null | Rule |
|---|---|---|---|
| `submitted_national_id` | text | no | Filled from `national_id_input` by the migration and at submission. Never changed ([R4](./research.md#r4-pinning-numbers)) |
| `submitted_family_number` | text | no | Filled from `family_number`. Never changed |
| `counts_commission` | boolean | no, default true | Set at accept. Only a `return` can be false ([R7](./research.md#r7-accept-with-the-commission-answer-and-with-warnings)) |
| `approval_warnings` | jsonb | yes | The warning kinds confirmed at accept, e.g. `["same_person"]` |
| `rejected_at` | timestamptz | yes | |
| `rejected_by` | bigint FK `users.id` | yes | |
| `rejection_reason` | text | yes | CHECK `IN ('card_unclear','numbers_mismatch','under_15_days','active_subscription','other')` ([R6](./research.md#r6-rejection-reasons-fr-019)) |
| `rejection_note` | text | yes | Only with `other`, 3 to 300 characters after trimming |

Values a pin may change: `national_id`, `family_number`, `family_key`, and `type` (`new` to
`additional` only).

New checks:
- `status = 'rejected'` ⇔ `rejected_at`, `rejected_by` and `rejection_reason` are set;
- `rejection_reason = 'other'` ⇔ `rejection_note` is set;
- `status = 'rejected'` ⇒ `approved_at IS NULL`.

The 008 checks still hold: `approved` has `approved_at`, `pending_review` has no `approved_at`.

New index: `requests_pending_idx (submitted_at) WHERE status = 'pending_review'`.

## request_reasons (changed)

| Column | Type | Null | Rule |
|---|---|---|---|
| `state` | text | no, default `'open'` | CHECK `IN ('open','resolved','not_applicable')` ([R3](./research.md#r3-reason-state)) |
| `state_changed_at` | timestamptz | yes | |
| `state_changed_by` | bigint FK `users.id` | yes | |
| `added_by` | bigint FK `users.id` | yes | null = recorded at submission, set = added by a re-check after a pin |

Arabic labels:
- `open`: no label;
- `resolved`: «تم التثبيت», only for `numbers_edited`;
- `not_applicable`: «لم يعد ينطبق».

## request_number_pins (new)

| Column | Type | Null | Rule |
|---|---|---|---|
| `id` | bigint identity | no | PK |
| `request_id` | bigint FK `requests.id` RESTRICT | no | |
| `field` | text | no | CHECK `IN ('national_id','family_number')` |
| `previous_value` | text | no | The field's value just before this pin (the before value for the audit, constitution III v1.2.1) |
| `value` | text | no | The pinned value (national ID normalized, family number as written) |
| `source` | text | no | CHECK `IN ('reading','mrz','marketer','typed')`. `mrz` is only for `national_id` |
| `pinned_by` | bigint FK `users.id` | no | |
| `pinned_at` | timestamptz | no | |

Index: `(request_id, pinned_at)`.

The table holds identity numbers and is append-only: there is no update or delete path. Only the
review pages read it. Its values never go into audit or log lines (Principle II). The audit entry
`request.numbers_pinned` holds `pin_id`, which makes the before and after values recoverable
(Principle III v1.2.1).

## image_access_log (changed)

| Column | Change |
|---|---|
| `draft_id` | becomes nullable |
| `request_id` | new, bigint, null, no FK (history outlives everything) |

A request image open writes both `request_id` and `draft_id = requests.draft_id`
([R9](./research.md#r9-image-access-for-review-fr-005)).

## In memory (not stored)

### ReviewCheck ([R5](./research.md#r5-re-check-and-warnings))

| Field | Meaning |
|---|---|
| `open_rows` | `(reason, source, ref)` for `family_exists` and `numbers_conflict` that apply now |
| `new_type` | `additional` if `type = 'new'` and a family-only match exists, else the current type |
| `warnings` | subset of `same_person`, `id_conflict`, `return_target_lost` |

### LinkedRecord ([R8](./research.md#r8-linked-records))

`source`, `ref`, `available`, `full_name`, `username`, `phone`, `tower_code`, `tower_name`,
`registered_at`, `status`, `image_ids`, `expiry` (null until 014).

## State transitions (§7.2)

```text
pending_review ──accept (review)──► approved   approved_at, approved_by, counts_commission, approval_warnings
pending_review ──reject (review)──► rejected   rejected_at, rejected_by, rejection_reason, rejection_note
pending_review ──pin (review)─────► pending_review   (numbers, type new→additional, reason states)
approved ──► linked ──► approved                    (012)
```

There is no move out of `rejected` and no move back to `pending_review`.
