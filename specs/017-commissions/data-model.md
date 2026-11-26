# Data Model: 017 Rewards and Commissions

Migration `0020_commissions` (revises `0019`). No change to `requests`, `request_links`, `reward_tiers`, the
legacy or SAS tables.

## New table `commission_payments`

One «تم الدفع» of one marketer for one Baghdad month. Never updated or deleted (Principle IV).

| Column | Type | Rules |
|---|---|---|
| `id` | bigint identity | primary key |
| `marketer_id` | bigint → `users.id` | not null; the account may later be archived, the row stays |
| `month` | date | not null; first day of the Baghdad month (`CHECK extract(day from month) = 1`) |
| `count` | integer | not null, `> 0` |
| `tier_min_count` | integer | not null, `>= 0`, `<= count` |
| `rate` | integer | not null, 1 … `MAX_AMOUNT` (as `reward_tiers`) |
| `amount` | bigint | not null, `= count * rate` |
| `paid_by` | bigint → `users.id` | not null |
| `paid_at` | timestamptz | not null, UTC |

- `UNIQUE (marketer_id, month)` — one payment per marketer and month (`already_paid`).
- Index on `month` (report by month).

## New table `commission_payment_requests`

The requests counted in a payment (FR-012, FR-016).

| Column | Type | Rules |
|---|---|---|
| `request_id` | bigint → `requests.id` | **primary key**: a request is in at most one payment |
| `payment_id` | bigint → `commission_payments.id` | not null, indexed |

- The number of rows of a payment equals its `count` (checked in the service and in tests).

## Derived values (not stored)

| Value | Rule |
|---|---|
| Month bounds | `baghdad_month_bounds(month)` — Baghdad midnight on the 1st, in UTC (Principle X) |
| Base set of a marketer month | requests of the marketer with `status = 'linked'`, `deleted_at IS NULL`, `linked_at` in the bounds |
| `paid_before` | base row with a `commission_payment_requests` entry |
| `without_commission` | other base row with `counts_commission = false` (return accepted with «لا») |
| `counted` | the rest (new, additional, return with «نعم») |
| Tier, amount, next tier | `core/commission.py` on `counted` and today's `reward_tiers` (unpaid months only) |
| Paid month figures | from `commission_payments`; today's count = its requests still linked with `linked_at` in that month |
| Alert line | `request_links` row `kind = 'unlinked'` of a paid request with `at > paid_at` |
| Payable | month finished (its end ≤ now), no payment yet, `counted > 0` |

## State of a marketer month

```text
open (current month) ──month ends──▶ unpaid ──«تم الدفع»──▶ paid (locked)
                                                               │
                                       undo of a paid request ─┴─▶ paid + alert (figures unchanged)
```

No transition back from paid (FR-013).

## Request (existing, unchanged)

Read only: `marketer_id`, `type`, `status`, `counts_commission`, `linked_at`, `deleted_at`, `number`,
`full_name`, `tower_name`, `tower_code`.
