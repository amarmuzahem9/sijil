# Data Model: Phone Verification by WhatsApp OTP (007)

Migration `0009_otp`. The shape of the table and of the two draft columns comes from the owner.

## New table `otp_challenges`

There is one row per **successful** send. A failed send writes nothing (research R6).

| Column | Type | Rules |
|---|---|---|
| `id` | uuid PK | Made in the app before hashing (it is part of the hashed message, R3) |
| `request_id` | uuid, null, FK `drafts.id` ON DELETE SET NULL | The draft. Named `request_id` because the draft row becomes the request in 008. Set to null when the draft is deleted, and the row stays so the hourly limit still counts it |
| `phone` | text, not null | Normalized `07XXXXXXXXX`, checked with `^07\d{9}$` |
| `code_hash` | text, not null | HMAC-SHA256 hex (R3). The plain code is never stored |
| `context_hash` | text, not null | SHA-256 hex of the phone, tower, category and both prices at send time (R4) |
| `expires_at` | timestamptz, not null | `created_at + otp_validity_minutes` (setting from 004, read at send) |
| `attempts` | int, not null, default 0 | Wrong entries. Check `0 ≤ attempts ≤ 3` |
| `verified_at` | timestamptz, null | Set once, by the correct entry |
| `created_at` | timestamptz, not null | Send time, from `utc_now()` |

Indexes:
- `otp_challenges_request_created_idx (request_id, created_at DESC)`: the newest code of a draft
  and the resend wait.
- `otp_challenges_phone_created_idx (phone, created_at DESC)`: the hourly limit.

### Derived state of a challenge (never stored)

| State | Condition |
|---|---|
| `verified` | `verified_at IS NOT NULL` |
| `cancelled` | `attempts >= 3`, or a newer row exists for the same `request_id`, or `context_hash` ≠ the draft's current context |
| `expired` | `now >= expires_at` |
| `active` | none of the above |

Only the newest row of a draft can be `active`.

## Changed table `drafts`

| Column | Type | Rules |
|---|---|---|
| `otp_verified_at` | timestamptz, null | Time of the last successful verification |
| `otp_context_hash` | text, null | The challenge's `context_hash` at that moment |

- Check: `(otp_verified_at IS NULL) = (otp_context_hash IS NULL)`.
- Both columns are set by a successful verify and cleared by any save that changes the context (R5).
- Writing them increments the draft `version` (optimistic concurrency from 005), so a second open
  device sees «تغيّرت المسودة من جهاز آخر» and loads the ✓.
- In 008, submission refreshes the copies, recomputes `context_hash`, and requires
  `otp_verified_at IS NOT NULL AND otp_context_hash = context_hash(draft)`. The submitted request
  then keeps `otp_verified_at` as a recorded fact (Principle IV).

## Draft status for the page: `DraftOut.otp`

| `status` | When | Extra fields |
|---|---|---|
| `none` | Never verified, no active code | — |
| `sent` | Newest code is `active` | `phone` (the number it was sent to), `resend_at`, `expires_at`, `attempts_left` |
| `verified` | `otp_verified_at` set and the context matches | `verified_at` |
| `needs_reverify` | Not verified now, no active code, and the draft has a challenge with `verified_at` set | — |

`resend_at` is also returned when the status is `none` or `needs_reverify` and the 60 s wait from
the last send is still running.

## Validation rules (from spec FRs)

- **Phone**: §8.1 normalization on the server. An invalid phone gives `invalid_phone` (FR-002).
- **Code entry**: Arabic-Indic digits are converted, spaces are removed, and the result must be
  exactly 6 digits. Otherwise `otp_code_format`, which does not use up an attempt.
- **Limits**: 60 s resend wait per draft, 5 sends per phone in any 60 minutes, 3 wrong attempts,
  expiry from the setting (R7).
