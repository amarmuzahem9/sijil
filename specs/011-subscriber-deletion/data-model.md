# Data Model: Subscriber Deletion (011)

Migration `0014_subscriber_deletion`. Design reasons are in [research.md](./research.md).

## `requests` (changed)

### New columns

| Column | Type | Rule |
|---|---|---|
| `deleted_at` | timestamptz, null | set once, never cleared |
| `deleted_by` | bigint → `users.id`, null | the admin who deleted |
| `deletion_reason` | text, null | `duplicate` \| `test` \| `entry_error` \| `other` |

### Columns made nullable (erased on deletion)

| Group | Columns |
|---|---|
| Names | `first_name`, `father_name`, `grandfather_name`, `great_grandfather_name`, `full_name`, `mother_first_name`, `mother_second_name`, `no_surname` |
| Identity | `national_id`, `national_id_input`, `submitted_national_id`, `family_number`, `submitted_family_number`, `family_key` |
| Card | `birth_date`, `issue_date`, `expiry_date`, `birth_place`, `issuing_authority`, `card_fields`, `card_readings` |
| Location | `location_lat`, `location_lng`, `location_source`, `address`, `landmark` |
| Contact | `phone`, `username` |

These columns are already nullable and are also erased: `surname`, `mother_third_name`,
`mother_surname`, `national_id_check`, `location_accuracy_m`, `rejection_note`.

### Kept on a deleted row

- `id`, `number`, `draft_id`, `marketer_id`, `type`, `status`;
- area, tower and plan: ids, names and codes;
- `trial_price`, `second_price`;
- `otp_verified_at`, `submitted_at`, `approved_*`;
- `rejected_at`, `rejected_by`, `rejection_reason`;
- `counts_commission`, `approval_warnings`;
- `created_at`, `updated_at`.

### Checks

- `requests_deletion_mark`: `(deleted_at IS NULL) = (deleted_by IS NULL) AND (deleted_at IS NULL) =
  (deletion_reason IS NULL)`.
- `requests_deletion_reason`: `deletion_reason IS NULL OR deletion_reason IN ('duplicate','test',
  'entry_error','other')`.
- `requests_deletable_status`: `deleted_at IS NULL OR status IN ('pending_review','rejected')`.
- `requests_erasure`, split into two parts:
  - when `deleted_at IS NULL`, every column made nullable above is `NOT NULL`;
  - when `deleted_at IS NOT NULL`, every erased column (both lists above) `IS NULL`.
- These existing checks are wrapped as `deleted_at IS NOT NULL OR (…)`: `requests_no_surname`,
  `requests_surname_required`, `requests_rejection_note`.

### Index

- `requests_pending_idx` partial condition becomes `status = 'pending_review' AND deleted_at IS NULL`.

## Rows removed on deletion (same transaction)

| Table | Which rows |
|---|---|
| `request_images` | all rows of the request (files unlinked after commit) |
| `request_number_pins` | all rows of the request |
| `otp_challenges` | `phone = <request phone> AND request_id IS NULL` |

## Rows kept unchanged

- `request_reasons`: these hold only codes, the matched reference, and `details` with field names or
  the return basis. There is no personal value to erase.
- `request_reasons` of other requests that point to the deleted one: unchanged.
- `audit_log`: never altered.
- `image_access_log`: holds ids only.

## `users` (changed)

- `users_permissions_known` gains `"delete"`.

## Lifecycle

```text
pending_review ──delete──▶ pending_review + deleted mark   (final)
rejected       ──delete──▶ rejected + deleted mark         (final)
approved, linked: delete refused
deleted: accept, reject, pin and delete refused (409 request_deleted)
```

## Deletion reasons

| Code | Arabic |
|---|---|
| `duplicate` | طلب مكرر |
| `test` | طلب تجريبي |
| `entry_error` | خطأ إدخال |
| `other` | سبب آخر |
