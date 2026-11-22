---

description: "Task list for feature 003: Account Archive"
---

# Tasks: Account Archive

**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution Principle VIII).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 [P] Add the `archive` page row (`/admin/archive`, `super_admin`) to `api/tests/fixtures/page_access.json` and the identical `web/src/__tests__/fixtures/page_access.json`. Regenerate the `cases` visible lists: the main admin sees `archive` and nobody else does (data-model.md › "Page map: new row")
- [X] T002 [P] Add the labels in `web/src/lib/labels.ts`: `user.archived` «أرشفة حساب», `user.restored` «استرجاع حساب من الأرشيف», and the field `archived` «مؤرشف» (data-model.md › "audit_log — actions added")

## Phase 2: Foundational

- [X] T003 Write migration `api/migrations/versions/0003_account_archive.py` (data-model.md › "users — new columns"):
  - add `users.archived_at` and `users.archived_by` (FK users.id)
  - add the CHECKs `users_archive_pair`, `users_archived_inactive`, `users_super_admin_not_archived`
  - replace `sessions_revoke_reason_valid` to add `archived`
  - provide a downgrade
  - mirror all of it in `api/app/models/user.py` and `api/app/models/session.py` (`REVOKE_REASONS`)
- [X] T004 [P] Add the page `archive: "super_admin"` to `api/app/core/access.py` and `web/src/auth/access.ts` (`PAGE_ACCESS`, `PAGE_PATHS`)
- [X] T005 Change `api/app/services/account_service.py`: `list_accounts` and `get_target` exclude rows where data-model.md › `users.archived_at` is set (research.md R2)

**Checkpoint**: The schema and access map are ready, and the 002 tests still pass.

## Phase 3: User Story 1 - Main admin archives an account (P1) 🎯 MVP

- [X] T006 [P] [US1] Integration tests in `api/tests/integration/test_archive.py` (archive part):
  - the main admin archives an active and a deactivated account
  - the target's token gets `account_inactive`, its sessions are revoked with reason `archived`, and login is refused
  - the account is gone from its list, and its 002 `/{id}` routes return 404
  - the main admin, an already-archived id, and an unknown id → 404
  - an admin with all permissions or a marketer → 403
  - one `user.archived` audit entry is written
- [X] T007 [US1] Add `archive(db, actor, target)` to `account_service.py`:
  - it sets data-model.md › `users.archived_at`, `users.archived_by` and `is_active = false`
  - it revokes sessions with `"archived"`
  - it writes the `user.archived` audit entry (research.md R5)
  - it does nothing on an already-archived row
  - it calls `ensure_not_protected`
- [X] T008 [US1] Create the router `api/app/api/archive.py` with `POST /admin/archive/{user_id}` (`require_roles("super_admin")`; the target is an admin or marketer that is not archived, else 404). Register it in `api/app/main.py`
- [X] T009 [US1] Add `accountsApi.archive(id)` in `web/src/lib/accounts.ts`. Add a «حذف» button, shown only when `user.role === 'super_admin'`, with a `ConfirmDialog` (research.md R6), in `web/src/pages/admin/Admins.tsx` and `web/src/pages/admin/Marketers.tsx`

## Phase 4: User Story 2 - «أرشيف الحسابات» page and restore (P1)

- [X] T010 [P] [US2] Add tests to `api/tests/integration/test_archive.py`:
  - `GET /api/admin/archive` lists newest first, with the archiver's name
  - restore → the account is back in its list with `is_active` false, and other fields are unchanged
  - login is still refused until reactivation through the 002 route
  - restore on an id that is not archived → 404
  - non-main-admin callers → 403
  - one `user.restored` audit entry is written
- [X] T011 [US2] Add `list_archived(db)` and `restore(db, actor, target)` to `account_service.py`, `ArchivedAccountOut` to `api/app/schemas/accounts.py`, and `GET /admin/archive` and `POST /admin/archive/{user_id}/restore` to `api/app/api/archive.py`
- [X] T012 [US2] Build the page `web/src/pages/admin/Archive.tsx`:
  - cards on a phone and a table from `md` up: name, phone, role, `formatBaghdad(archived_at)`, archiver
  - a «استرجاع» button
  - the empty state «لا توجد حسابات مؤرشفة»
  - the snackbar «تم الاسترجاع، الحساب موقوف حتى تفعّله»
- [X] T013 [US2] Wire the page in:
  - add the route `page('archive', …)` in `web/src/router.tsx`
  - add the menu item «أرشيف الحسابات» after «سجل العمليات» in `web/src/layouts/AdminLayout.tsx`
  - add it to `ADMIN_PAGES` in `e2e/tests/helpers.ts`

## Phase 5: User Story 3 - History and phone stay (P2)

- [X] T014 [P] [US3] Add tests to `api/tests/integration/test_archive.py`:
  - creating or editing an account with an archived phone → 409 `phone_taken`
  - the audit viewer still shows the archived account's name as actor and target
  - the archived account is still listed in `/api/admin/audit/actors`

## Phase 6: Polish

- [X] T015 [P] Write the Playwright test `e2e/tests/archive.spec.ts` (quickstart A–E):
  - archive a signed-in synthetic marketer
  - the archive page shows it
  - restore → «موقوف»
  - reactivate → sign-in works
  - a `marketers` admin sees no «حذف» and no archive page
- [X] T016 Run `scripts/test-all.sh`. Then run `docker compose up`, check the running app, and write `specs/003-account-archive/manual-test-ar.md`. Add 003 to the README feature table

## Implementation notes (2026-11-22)

- Full gate green: ruff, pytest 193 (12 new in `test_archive.py`), eslint (1 pre-existing warning), typecheck, vitest 64, Playwright 16 (new `archive.spec.ts`).
- Migration `0003` verified up → down → up on the dev database.
- `docs/system.md` v1.2 (§3.6, §10 page 12, §16 renumbered) and constitution 1.1.0 (Principle III) were amended before the spec, as the owner asked.
