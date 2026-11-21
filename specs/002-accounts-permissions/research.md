# Research: Accounts & Permissions (002)

No open technical questions remained after the spec clarifications. The items below record the
design decisions, built on what feature 001 already provides.

## R1. Where permissions are checked

- **Decision**: A FastAPI dependency `require_permission(*perms)` in `api/app/api/deps.py`. It
  builds on `current_user`, passes for `super_admin`, and passes for `admin` when the caller holds
  **any** of `perms`. Main-admin-only routes keep `require_roles("super_admin")`. One module,
  `api/app/core/access.py`, holds the page→permission map of system.md §10 (v1.1) as data, and the
  routers use it.
- **Rationale**: `current_user_allow_password_change` already loads the `User` row from the
  database on every request (001), so permission changes take effect on the next request with no
  token change (FR-003). An any-of check expresses «المشتركون» (`review` | `link` | `reports`).
- **Alternatives**: Permissions inside the JWT were rejected because they stay stale for up to 15
  minutes and break FR-003. Per-route ad-hoc checks were rejected because they are easy to forget
  (Principle IX).

## R2. Keeping the web menu in sync with permission changes

- **Decision**: The web keeps `/api/auth/me` in a TanStack Query (`['me']`). It is refetched on
  every route change and on window focus. Any `forbidden` (403) response also triggers a refetch.
  `AuthProvider` exposes the fresh user. The menu and route guards read
  `web/src/auth/access.ts`, which mirrors `access.py`. Both sides are tested against one shared
  fixture, `page_access.json`, copied to `api/tests/fixtures/` and `web/src/__tests__/fixtures/`
  in the same way as `phone_cases.json` in 001.
- **Rationale**: This meets SC-007 (menu updated on the next page load) without polling. `/me` is a
  single indexed lookup.
- **Alternatives**: Server-sent events or WebSocket push were rejected as unnecessary
  infrastructure (Principle VI). Periodic polling was rejected as wasteful on weak networks.

## R3. Deactivation and immediate session end

- **Decision**: Deactivation sets `is_active = false` and, in the same transaction, calls the
  existing `auth_service.deactivate_user_sessions(user_id, "deactivated")`. Reactivation only sets
  `is_active = true`, so the user must sign in again. A password reset by an admin sets the new
  hash and `must_change_password = true`, and revokes all sessions with reason `password_reset`.
- **Rationale**: Every request already rejects inactive users (`account_inactive`, 403). The web
  then clears its state and shows «الحساب موقوف، راجع الإدارة» (001 behaviour). Revoking the
  sessions too means that a reactivation does not bring old devices back to life.
- **Alternatives**: Relying on `is_active` alone was rejected because a reactivation would
  silently restore old sessions.

## R4. Protecting the main admin

- **Decision**: The admin-management routes only operate on rows with `role = 'admin'`. The
  marketer-management routes only operate on `role = 'marketer'`. Any other target returns 404
  `not_found`, so these routes can never touch the main admin or an account of the other role.
  `super_admin` keeps `permissions = []` in storage (implicit all, as in 001). There is no API
  that changes `role`. A service-level guard `ensure_not_protected` is still called before
  deactivate, reset, and permission changes, as defence in depth (403 `protected_account`).
- **Rationale**: This covers FR-002, FR-008, and SC-004 structurally, not just through UI hiding.
  Because no route reaches it, the main admin can never be deactivated, so "at least one active
  main admin" holds.

## R5. Validation and uniqueness

- **Decision**: Pydantic schemas trim the name and check its length (2–100). The phone goes
  through `normalize_phone` (`invalid_phone`, 422). Temporary passwords must be at least 8
  characters (`weak_password`). Permissions must be a subset of the six keys with no duplicates
  and are stored in canonical order. Uniqueness: the service checks first, and the unique index
  on `users.phone` is the source of truth. `IntegrityError` maps to 409 `phone_taken` «رقم الهاتف
  مستخدم لحساب آخر».
- **Migration `0002`**: adds a CHECK constraint so that `permissions` contains only the known keys
  (`permissions <@ '["review","link","settings","marketers","reports","commissions"]'`). It also
  adds an index `audit_log (actor_id, created_at DESC)` for the audit filter. There are no new
  tables.

## R6. Audit actions and the audit viewer

- **Decision**: These actions are added. Each successful change writes one entry, and a PATCH that
  changes both details and permissions writes two (`user.updated` + `user.permissions_changed`):

  | action | before / after |
  |---|---|
  | `user.created` | after `{name, phone, role, permissions, is_active, must_change_password}` |
  | `user.updated` | changed subset of `{name, phone}` (also the main admin's own name edit) |
  | `user.permissions_changed` | `{permissions}` before/after |
  | `user.deactivated` / `user.reactivated` | `{is_active}` before/after |
  | `user.password_reset` | `{must_change_password}` before/after (no password data) |

  No-op requests (deactivating an already inactive account, or a PATCH that changes nothing)
  return 200 and write nothing. The existing `_clean()` allow-list still strips any
  password/token/hash key.
- **Viewer**: `GET /api/admin/audit` is main admin only. It returns entries newest first with
  keyset pagination (`before_id`, page size 50, `has_more`) and is filtered by Baghdad dates
  (`from`/`to`, inclusive). The dates are converted with a new helper,
  `timeutil.baghdad_day_bounds()`. It can also be filtered by `actor_id` (`system` = null actor).
  Each entry carries the actor and target display names (joined from `users`), so the page needs
  one call. `GET /api/admin/audit/actors` feeds the actor filter. The web maps action codes and
  field names to Arabic labels.
- **Rationale**: Keyset pagination stays fast and stable while new entries arrive. Offset paging
  would shift rows.

## R7. «حسابي» name edit for the main admin

- **Decision**: `PATCH /api/auth/me` accepts `{name}` only. A `super_admin` caller gets the name
  updated and a `user.updated` audit entry. Any other role gets 403 `forbidden`. The phone has no
  edit endpoint for its owner in any role.

## R8. Concurrency

- **Decision**: Last write wins. There is no optimistic locking (spec edge case). Each write runs
  in its own transaction, and both writes are audited.

## R9. Error message wording

- **Decision**: The existing `forbidden` message from 001, «ليس لديك صلاحية لهذه الصفحة», becomes
  the shorter «ليست لديك صلاحية» so it also fits actions, as worded in the spec. New codes:
  `phone_taken` (409), `protected_account` (403), `invalid_name` (422). `not_found` is reused.

## R10. Frontend screens

- **Decision**: These are built from MUI components already in use:
  - On a phone, lists are cards. From `md` up, they are tables.
  - Add and edit happen in a dialog (full-screen on a phone).
  - The six permissions are `Switch` rows with their Arabic labels.
  - Deactivation and reset need a confirmation dialog.
  - The temporary password field has show/hide. It is not stored on the client after submit and
    is not cleared into any toast.
  - The audit list uses «تحميل المزيد» paging, with date and actor filters at the top.
  - The before/after values are shown as two short labelled lists.
- **Tests**: Vitest covers the access map and menu filtering. Playwright covers the acceptance path
  and the deactivation path (see quickstart.md).
