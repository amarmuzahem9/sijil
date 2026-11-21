# Data Model: Project Skeleton & Sign-In (001)

All timestamps are `timestamptz`, stored in UTC (Principle X). Rows in `users` and `audit_log` are
never physically deleted (Principle III).

## users

| Column | Type | Rules |
|---|---|---|
| `id` | bigint identity PK | |
| `name` | text, not null | 2–100 chars, trimmed |
| `phone` | text, not null, **unique** | Stored normalized only; must match `^07\d{9}$` (CHECK constraint) |
| `password_hash` | text, not null | Argon2id encoded string |
| `role` | text, not null | CHECK in (`super_admin`, `admin`, `marketer`) |
| `permissions` | jsonb, not null, default `[]` | List of strings, each in (`review`, `link`, `settings`, `marketers`, `reports`, `commissions`); MUST be `[]` unless `role = admin`. Managed in feature 002 |
| `is_active` | boolean, not null, default true | false = deactivated; cannot sign in |
| `must_change_password` | boolean, not null, default false | true after bootstrap or admin reset |
| `failed_logins` | smallint, not null, default 0 | Consecutive failures; reset on success |
| `locked_until` | timestamptz, null | Sign-in refused while `now() < locked_until` |
| `created_at` | timestamptz, not null, default now() | |
| `updated_at` | timestamptz, not null, default now() | Set on every update (added beyond the owner's list to support audit before/after) |

Indexes: unique `users_phone_key (phone)`, plus a partial index on `role` where
`role = 'super_admin'` (used by bootstrap).

Validation (application level):
- The phone passes `normalize_phone` before insert or lookup.
- The password policy is a minimum of 8 characters and must differ from the current password
  (FR-012).
- At least one active `super_admin` must always exist. Enforced in feature 002 when deactivation
  becomes possible; noted here as an invariant.

### Lockout state

```text
failed_logins = n (0..4), locked_until = null
  ── wrong password ──▶ n+1; if n+1 = 5 → locked_until = now + 15 min, failed_logins = 0, audit user.locked
  ── correct password ──▶ failed_logins = 0
locked (now < locked_until)
  ── any attempt ──▶ refused 423, no state change
  ── time passes ──▶ unlocked (evaluated lazily on next attempt)
```

## sessions

One row per signed-in device (refresh-token family). Added beyond the owner's list. It is required
for per-device sign-out (FR-009) and to revoke all sessions on password change, reset, or
deactivation (FR-007, FR-012).

| Column | Type | Rules |
|---|---|---|
| `id` | uuid PK | Embedded as `sid` in access tokens |
| `user_id` | bigint FK → users.id, not null | index |
| `refresh_token_hash` | text, not null, unique | SHA-256 hex of the current refresh token |
| `created_at` | timestamptz, not null | |
| `last_used_at` | timestamptz, not null | Updated on each refresh |
| `expires_at` | timestamptz, not null | `last_used_at + 30 days` (sliding) |
| `revoked_at` | timestamptz, null | Set on sign-out, reuse detection, password change, or deactivation |
| `revoke_reason` | text, null | `logout`, `password_changed`, `password_reset`, `deactivated`, `reuse_detected` |
| `user_agent` | text, null | Truncated to 255 chars; display only |

A session is **valid** when `revoked_at IS NULL AND now() < expires_at` and the user is active.
Expired and revoked rows are kept and may be purged by a later maintenance task. They hold no
personal data beyond the user agent.

## audit_log

Columns as requested by the owner. Append-only: the application never updates or deletes rows.

| Column | Type | Rules |
|---|---|---|
| `id` | bigint identity PK | |
| `actor_id` | bigint FK → users.id, null | null = system (e.g., bootstrap) |
| `action` | text, not null | Dotted verb, see below |
| `entity_type` | text, not null | e.g. `user` |
| `entity_id` | text, not null | |
| `before` | jsonb, null | Changed fields before; **never** secrets |
| `after` | jsonb, null | Changed fields after; **never** secrets |
| `created_at` | timestamptz, not null, default now() | index (desc) |

Actions written in feature 001:

| action | actor | before / after |
|---|---|---|
| `user.bootstrap_created` | null | after: `{name, phone, role}` |
| `user.locked` | null | after: `{locked_until}` |
| `user.password_changed` | the user | before: `{must_change_password}`, after: `{must_change_password: false}` (no password data) |

Password hashes, tokens, and OTPs are excluded from `before`/`after` by an allow-list serializer.

## Role → landing page

| role | landing | label (Arabic) |
|---|---|---|
| `super_admin` | `/admin` | أدمن رئيسي |
| `admin` | `/admin` | أدمن |
| `marketer` | `/` (marketer dashboard) | مسوّق |
