# Research: Account Archive (003)

## R1. How "archived" is stored

- **Decision**: Two nullable columns are added to `users`:
  - `archived_at` (timestamptz)
  - `archived_by` (FK → users.id)

  Archiving also sets `is_active = false`.
- **Rationale**: Sign-in and `current_user` already refuse inactive accounts with
  `account_inactive` (the 002 ordering puts inactive before session validity). So archived
  accounts are refused everywhere with no new checks, and they get the message the spec asks for.
  Restore clears the archive mark and leaves `is_active = false`, which satisfies "restored as
  deactivated".
- **Alternatives**: A separate `archived_accounts` table was rejected because the row would move
  and break name joins (FR-009). A `status` enum was rejected because it would touch every 001/002
  check.

## R2. Keeping archived rows out of the 002 routes

- **Decision**: In `account_service`, `list_accounts` and `get_target` exclude
  `archived_at IS NOT NULL`. As a result, the admins and marketers routes return 404 for archived
  ids: no edit, deactivate, reactivate or reset (FR-004). Only the archive routes reach archived
  rows.
- **Rationale**: This is one choke point that is already used by every 002 route.

## R3. Sessions

- **Decision**: `deactivate_user_sessions(user_id, "archived")`, so a new revoke reason is needed.
  Migration `0003` replaces the `sessions_revoke_reason_valid` CHECK to allow it.

## R4. Routes

- **Decision**: Every route is main admin only (`require_roles("super_admin")`):
  - `POST /api/admin/archive/{user_id}` archives an admin or marketer that is not archived.
    Otherwise it returns 404.
  - `GET /api/admin/archive` lists archived accounts, newest archive first, with the archiver's
    name.
  - `POST /api/admin/archive/{user_id}/restore` restores an account. A target that is not
    archived returns 404.
- The main admin is never a valid target: the role must be `admin` or `marketer`, and a DB CHECK
  also enforces it (`role <> 'super_admin' OR archived_at IS NULL`).
- No-ops cannot occur through these routes (404 instead). The service still returns without
  auditing if called on an already-archived row.

## R5. Audit

- **Decision**:
  - `user.archived` with before `{is_active, archived: false}` and after
    `{is_active: false, archived: true}`.
  - `user.restored` with before `{archived: true}` and after `{archived: false}`.
- **Labels** (web):
  - Action: «أرشفة حساب» and «استرجاع حساب من الأرشيف».
  - Field: `archived` «مؤرشف», shown as نعم/لا.
- The audit viewer needs no change for names: it joins `users`, and archived rows still exist.

## R6. UI

- **Decision**:
  - «حذف» is rendered on the admins and marketers rows only when `user.role === 'super_admin'`.
  - It opens a `ConfirmDialog` with the text «نقل حساب <الاسم> إلى الأرشيف؟ سيُسجَّل خروجه فوراً
    ولن يستطيع الدخول، ويمكن استرجاعه من «أرشيف الحسابات».».
  - The new page `/admin/archive` (page key `archive`, main admin only) is added to the shared
    access fixture and the menu after «سجل العمليات».
  - Restore asks for no confirmation. Its snackbar reads «تم الاسترجاع، الحساب موقوف حتى تفعّله».
