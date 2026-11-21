# Implementation Plan: Accounts & Permissions

**Branch**: `002-accounts-permissions` | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-accounts-permissions/spec.md`

## Summary

This feature adds account management to the 001 skeleton:
- The main admin creates and edits admins, chooses their permissions with six Arabic-labelled
  switches, deactivates and reactivates them, and resets their passwords.
- Holders of `marketers` do the same for marketers, except permissions.
- Every user has a read-only «حسابي» page with a password change. The main admin can also edit
  their own name.
- Every change is audited, and the main admin has a read-only «سجل العمليات» viewer with date and
  actor filters.

**Server**:
- A `require_permission(any-of)` dependency checks the permissions of system.md §10 v1.1 on every
  request.
- Permissions are read fresh from the database each request, so changes apply at once.
- Deactivation and reset revoke all sessions through the existing
  `deactivate_user_sessions`.
- The main admin is structurally unreachable from the management routes.

**Web**:
- Menu and route guards filter pages through the same access map, tested against a shared
  fixture.
- `/me` is refetched on navigation so permission changes show without signing out.

There are no new tables. Migration `0002` adds one CHECK constraint and one index. Details:
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web), as in 001

**Primary Dependencies**: Unchanged from 001: FastAPI, SQLAlchemy 2, Alembic, Pydantic v2,
argon2-cffi, React Router, TanStack Query, and MUI with RTL. There are no new packages.

**Storage**: PostgreSQL 16. The existing tables are `users`, `sessions`, and `audit_log`.
Migration `0002` adds a permissions CHECK constraint and the index
`audit_log (actor_id, created_at DESC)`.

**Testing**: pytest against a real PostgreSQL database, Vitest with Testing Library, and Playwright
(desktop Chrome and Pixel 7)

**Target Platform**: Unchanged. Docker Compose on the company Linux server, phones and desktop
browsers.

**Project Type**: Web application (the `api/` and `web/` monorepo)

**Performance Goals**: Adding a marketer takes under 1 minute on a phone (SC-006). Finding an
audit entry by date and actor takes under 30 s (SC-008). Each audit page is 50 rows.

**Constraints**:
- Authorization is enforced on the server for every route.
- Passwords never appear in audit entries, logs, or responses.
- Times are stored in UTC and shown in Baghdad time. Audit date filters use Baghdad days.

**Scale/Scope**: Tens of marketers and a few admins. The feature adds 3 admin screens and changes
«حسابي». It adds about 15 API routes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | Phones are normalized on the server per §8.1 and are unique across all accounts. No request decisions are involved |
| II. Identity Documents | ✅ | Passwords use Argon2id. Temporary passwords are never echoed, logged, or audited (`_clean()` allow-list, tested). There is no card data |
| III. Audit Trail | ✅ | Every account change writes an entry with before/after. The viewer is read-only and no write or delete route exists. Accounts are never deleted |
| IV. Immutable Values | ✅ (N/A) | No priced or decided records |
| V. Mobile-First & Arabic | ✅ | Lists are cards and dialogs are full-screen on a phone. Labels are Arabic and the layout RTL. Errors are clear Arabic messages |
| VI. Simplicity | ✅ | Only the spec scope and the owner decisions now in system.md v1.1. No new tables or services. Last write wins |
| VII. Fixed Stack | ✅ | No new dependencies. Configuration is unchanged |
| VIII. Tests | ✅ | pytest covers the authorization matrix, protection, uniqueness, revocation, and audit. Playwright covers the acceptance path and deactivation |
| IX. Server Authorization | ✅ | `require_permission` / `require_roles` on every route. Role-scoped targets (R4). The UI hiding is only convenience |
| X. Time | ✅ | Timestamps are UTC. `baghdad_day_bounds()` drives the audit filter, and display uses `formatBaghdad` |

**Result (pre-research)**: PASS. **Result (post-design)**: PASS. There are no violations, so the
Complexity Tracking table is not needed. Rule changes were made in `docs/system.md` (v1.1) before
the plan.

## Project Structure

### Documentation (this feature)

```text
specs/002-accounts-permissions/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md
│   └── ui-routes.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
api/
├── app/
│   ├── core/
│   │   ├── access.py              # NEW: page→permission map, PERMISSION_LABELS
│   │   └── timeutil.py            # + baghdad_day_bounds()
│   ├── api/
│   │   ├── deps.py                # + require_permission(*perms)
│   │   ├── admins.py              # NEW: /api/admin/admins*
│   │   ├── marketers.py           # NEW: /api/admin/marketers*
│   │   ├── audit.py               # NEW: /api/admin/audit, /audit/actors
│   │   └── auth.py                # + PATCH /api/auth/me (main admin name)
│   ├── schemas/
│   │   ├── accounts.py            # NEW: create/update/reset bodies, AccountOut
│   │   └── audit.py               # NEW: AuditEntryOut, page shape
│   ├── services/
│   │   ├── account_service.py     # NEW: create/update/deactivate/reactivate/reset + audit
│   │   └── audit_query.py         # NEW: filtered keyset listing
│   ├── errors.py                  # + phone_taken, protected_account, invalid_name; forbidden wording
│   └── main.py                    # register new routers
├── migrations/versions/0002_permissions_check_audit_index.py
└── tests/
    ├── fixtures/page_access.json  # NEW: shared with web
    ├── unit/test_access.py, test_timeutil.py (+ day bounds)
    └── integration/test_admins.py, test_marketers.py, test_authz_matrix.py,
        test_account_sessions.py, test_audit_viewer.py, test_me_name.py

web/src/
├── auth/access.ts                 # NEW: mirror of access.py + permission labels
├── auth/AuthProvider.tsx          # /me as a query, refetch on route change and on 403
├── auth/guards.tsx                # + RequirePage
├── layouts/AdminLayout.tsx        # menu filtered by access map
├── lib/accounts.ts, lib/audit.ts  # NEW: typed API calls
├── components/AccountDialog.tsx, ConfirmDialog.tsx, PermissionSwitches.tsx  # NEW
├── pages/admin/Admins.tsx, Marketers.tsx, Audit.tsx                        # NEW (replace placeholders)
├── pages/AccountPanel.tsx         # read-only + main-admin name edit
├── router.tsx                     # per-page guards
└── __tests__/access.test.ts, fixtures/page_access.json

e2e/tests/accounts-acceptance.spec.ts, deactivation.spec.ts                 # NEW
```

**Structure Decision**: Keep the 001 monorepo layout. The new routers sit next to `admin.py`,
and the business rules live in `account_service.py` so the routers stay thin. The access map is
data on both sides, and one shared fixture checks that the two copies match.

## Complexity Tracking

No constitution violations. This section is intentionally empty.
