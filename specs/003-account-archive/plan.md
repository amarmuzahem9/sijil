# Implementation Plan: Account Archive

**Branch**: `003-account-archive` | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-account-archive/spec.md`

## Summary

«حذف» (main admin only) moves an admin or marketer to a reversible archive:
- The account gets the columns `archived_at` and `archived_by`.
- It is also set inactive, so the existing sign-in and per-request checks refuse it with
  «الحساب موقوف، راجع الإدارة».
- Its sessions are revoked with the reason `archived`.
- The role-scoped account routes of feature 002 stop seeing archived rows, so archived accounts
  leave the lists and cannot be edited.

A new main-admin-only page, «أرشيف الحسابات», lists archived accounts and restores them. A
restored account comes back deactivated. Both actions are audited. The phone stays reserved
through the existing unique index. Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web), unchanged

**Primary Dependencies**: Unchanged from 002. There are no new packages.

**Storage**: PostgreSQL 16. Migration `0003` changes these tables:
- `users`: new columns `archived_at` and `archived_by`, with CHECK constraints.
- `sessions`: a new revoke reason, `archived`.

**Testing**: pytest (real PostgreSQL), Vitest (access map fixture), Playwright (archive flow)

**Target Platform / Project Type**: Unchanged (Docker Compose web app, `api/` + `web/`)

**Performance Goals**: Archiving takes under 15 s in the UI (SC-001). The archive list is a single
small query.

**Constraints**:
- Authorization is enforced on the server.
- Nothing is physically deleted.
- Times are stored in UTC and shown in Baghdad time.

**Scale/Scope**: 1 new page, 2 changed pages, and 3 new API routes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud | ✅ | An archived phone stays reserved (the unique index covers every row) |
| II. Identity Documents | ✅ | No card data. No secrets in the audit log |
| III. Audit Trail (1.1.0) | ✅ | The amendment is in place before the plan. Archiving is a reversible mark, never a delete. Archive and restore are audited. Names stay joinable |
| IV. Immutable Values | ✅ (N/A) | Nothing is priced or decided |
| V. Mobile & Arabic | ✅ | Cards on a phone, Arabic RTL, confirmation dialog |
| VI. Simplicity | ✅ | Two columns and a reuse of `is_active`. No archive table |
| VII. Fixed Stack | ✅ | No new dependencies |
| VIII. Tests | ✅ | pytest covers the rules and authorization. Playwright covers the archive and restore flow |
| IX. Server Authorization | ✅ | `require_roles("super_admin")` on every archive route. Role-scoped targets exclude archived rows |
| X. Time | ✅ | `archived_at` is UTC and shown with `formatBaghdad` |

**Result**: PASS before research and after design.

## Project Structure

```text
specs/003-account-archive/  plan.md research.md data-model.md quickstart.md contracts/ tasks.md

api/app/models/user.py, session.py              # archived_at/archived_by, revoke reason
api/migrations/versions/0003_account_archive.py
api/app/services/account_service.py              # archive(), restore(), list_archived(); exclusions
api/app/schemas/accounts.py                      # ArchivedAccountOut
api/app/api/archive.py                           # /api/admin/archive*
api/app/core/access.py                           # page "archive" (super_admin)
api/tests/fixtures/page_access.json + web copy   # + archive page
api/tests/integration/test_archive.py
web/src/auth/access.ts, layouts/AdminLayout.tsx, router.tsx
web/src/lib/accounts.ts, lib/labels.ts
web/src/pages/admin/Archive.tsx, Admins.tsx, Marketers.tsx
e2e/tests/helpers.ts (ADMIN_PAGES), e2e/tests/archive.spec.ts
```

**Structure Decision**: This feature extends the 002 modules in place. There is one new router
and one new page.

## Complexity Tracking

No violations.
