---

description: "Task list for feature 002: Accounts & Permissions"
---

# Tasks: Accounts & Permissions

**Input**: Design documents from `specs/002-accounts-permissions/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md),
[contracts/ui-routes.md](./contracts/ui-routes.md), [quickstart.md](./quickstart.md)

**Tests**: Required. Constitution Principle VIII asks for pytest on permissions and Playwright on
critical flows. Write each test task first and confirm it fails.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested on
its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md
- Paths follow plan.md: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Shared fixtures and labels that every story reads.

- [X] T001 [P] Create the shared page-access fixture in `api/tests/fixtures/page_access.json` and an identical copy in `web/src/__tests__/fixtures/page_access.json`. It holds the page key, path, and access (`any_admin`, `super_admin`, or a list of permissions, any-of) for all 12 rows of data-model.md › "Permission ⇄ page map", plus cases per permission set (none, `[marketers]`, `[review]`, `[link]`, `[reports]`, all six, super_admin) with the expected visible pages
- [X] T002 [P] Create the Arabic label maps in `web/src/lib/labels.ts`: permission labels (data-model.md › "Arabic permission labels"), audit action labels, and before/after field labels (data-model.md › "audit_log — actions added")

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Authorization, validation, the account service, and the permission-aware shell. Every story depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests (write first)

- [X] T003 [P] Unit test of the access map against `api/tests/fixtures/page_access.json` in `api/tests/unit/test_access.py`. It covers `can_access(role, permissions, page)` for every fixture case
- [X] T004 [P] Unit tests for `baghdad_day_bounds(from_date, to_date)` in `api/tests/unit/test_timeutil.py`: an inclusive Baghdad day becomes UTC `[start, end)`; a single day; the turn of a month
- [X] T005 [P] Integration tests for `require_permission` in `api/tests/integration/test_require_permission.py`. Use a throwaway test-only router mounted in the test:
  - super_admin passes, a marketer gets 403, an admin passes only with one of the listed permissions
  - after a DB update of `permissions` the next request is evaluated with the new list, with no new sign-in (FR-003)
  - the `forbidden` message is «ليست لديك صلاحية»
- [X] T006 [P] Integration tests for `account_service` in `api/tests/integration/test_account_service.py`:
  - phone normalized and unique across roles and states (409 `phone_taken`, including an `IntegrityError` race)
  - name trimmed and 2–100 chars → `invalid_name` with its Arabic message (not the generic `validation_error`); temporary password < 8 → `weak_password`, on create and on reset
  - create sets `must_change_password`
  - deactivate revokes every session (reason `deactivated`); reactivate leaves sessions revoked
  - reset sets the hash and the flag and revokes sessions (reason `password_reset`)
  - no-ops write no audit entry; one audit entry per change; no password/hash/token in any audit `before`/`after`
  - `ensure_not_protected` refuses a super_admin target (403 `protected_account`)
- [X] T007 [P] Vitest for `web/src/auth/access.ts` against `web/src/__tests__/fixtures/page_access.json`, and for menu filtering of `AdminLayout` per permission set, in `web/src/__tests__/access.test.tsx`

### Implementation

- [X] T008 Alembic migration `api/migrations/versions/0002_permissions_check_audit_index.py` (data-model.md › "Migration 0002"). It adds the CHECK `users_permissions_known` for data-model.md › `users.permissions` and the index `audit_log_actor_created_idx`, with a working downgrade. Mirror both in `api/app/models/user.py` and `api/app/models/audit.py` `__table_args__`
- [X] T009 [P] Create `api/app/core/access.py`. It holds:
  - `PAGE_ACCESS`, the page key → access rule of data-model.md › "Permission ⇄ page map"
  - `can_access(role, permissions, page)`
  - `normalize_permissions(list)`, which deduplicates, orders canonically like `ADMIN_PERMISSIONS`, and rejects unknown keys (data-model.md › `users.permissions`)
- [X] T010 [P] Add `baghdad_day_bounds()` in `api/app/core/timeutil.py`
- [X] T011 [P] Error codes in `api/app/errors.py` (contracts/api.md › "New and changed error codes"):
  - change the `forbidden` message to «ليست لديك صلاحية»
  - add `phone_taken`, `protected_account`, `invalid_name`
  - update the expected text in existing 001 tests (`api/tests/integration/test_roles.py` and any e2e assertion in `e2e/tests/`)
- [X] T012 Add `require_permission(*perms)` to `api/app/api/deps.py`. It builds on `current_user`; super_admin always passes, admin passes with any-of, marketer is refused (research.md R1). Depends on T009, T011
- [X] T013 [P] Pydantic schemas in `api/app/schemas/accounts.py`:
  - `AccountOut` (contracts/api.md › "Shared shapes")
  - `AdminCreate`, `AdminUpdate`, `MarketerCreate`, `MarketerUpdate`, `ResetPasswordBody`, `NameUpdate`, with `extra="forbid"`
  - types only: `name`, `phone`, `temporary_password` are plain `str` fields with no length rules here, so the service can return the specific error codes (fix I1); `permissions` only on admin bodies
- [X] T014 Implement `api/app/services/account_service.py`. Depends on T008, T009, T011, T013.
  - Functions: `create_account(role, ...)`, `update_account(target, name?, phone?, permissions?)`, `set_active(target, active)`, `reset_password(target, temp)`, `ensure_not_protected(target)`, `get_target(db, id, role)`. The last returns 404 `not_found` when the role does not match (research.md R4).
  - Validation per data-model.md › `users.name` (trim, 2–100 → 422 `invalid_name`), data-model.md › `users.password_hash` (temporary password ≥ 8 → 422 `weak_password`), `users.phone` (normalize_phone → `invalid_phone`, uniqueness → `phone_taken`), `users.role` (fixed at creation, never updated), `users.permissions` (admins only), `users.is_active`, `users.must_change_password`.
  - Uses `auth_service.deactivate_user_sessions` and `hash_password`.
  - Writes the audit actions of data-model.md › "audit_log — actions added" through `audit_service.record`, one entry per change kind and none on no-ops (research.md R6). Catch `IntegrityError` on phone → `phone_taken`.
- [X] T015 [P] Create `web/src/auth/access.ts`: the mirror of `PAGE_ACCESS`, `canAccess(user, pageKey)`, and `pageKeyForPath(path)`
- [X] T016 Make `/api/auth/me` a TanStack query `['me']` in `web/src/auth/AuthProvider.tsx` (research.md R2). It refetches on route change (location listener) and on window focus, and the user from the query feeds the context. Also extend `web/src/lib/api.ts` so a `forbidden` 403 invalidates `['me']`
- [X] T017 Add `RequirePage({page})` in `web/src/auth/guards.tsx`. Without access it does `<Navigate to="/admin">` and shows the snackbar «ليست لديك صلاحية». Use it in `web/src/router.tsx` for every `/admin/*` child, replacing the `RequireRole(['super_admin'])` wrapper on `admins` (contracts/ui-routes.md › "Route access"). Depends on T015
- [X] T018 Filter `ADMIN_PAGES` in `web/src/layouts/AdminLayout.tsx` with `canAccess` instead of `superAdminOnly`. Depends on T015
- [X] T019 [P] Shared UI components:
  - `web/src/components/ConfirmDialog.tsx`
  - `web/src/components/PermissionSwitches.tsx`: six MUI `Switch` rows with labels from `web/src/lib/labels.ts`
  - `web/src/components/AccountDialog.tsx`: fields name, phone (LTR, inline «رقم غير صالح» via `web/src/lib/phone.ts`), optional temporary password with show/hide, optional permissions slot; full-screen below `md`
  - `web/src/components/ResetPasswordDialog.tsx`
- [X] T020 [P] Typed API calls in `web/src/lib/accounts.ts`: an `Account` type, plus list/create/update/deactivate/reactivate/resetPassword for admins and marketers (contracts/api.md)

**Checkpoint**: The permission checks and the menu filtering run, and the account service is tested. Story work can start.

---

## Phase 3: User Story 1 - Main admin adds an admin with chosen permissions (Priority: P1) 🎯 MVP

**Goal**: The main admin creates an admin with chosen switches. That admin sees only the permitted pages.

**Independent Test**: Create an admin with only `marketers`, sign in as them, change the password, and check that the menu has المسوّقون and no الإعدادات. `/admin/settings` redirects, and the API returns 403.

### Tests for User Story 1

- [X] T021 [P] [US1] Integration tests in `api/tests/integration/test_admins.py`:
  - `POST/GET /api/admin/admins` as super_admin: 201 `AccountOut`, role admin, the given permissions, `must_change_password` true, `user.created` audit
  - duplicate phone in another format → 409
  - an unknown permission key → 422
  - marketer and admin callers (even with every permission) → 403
  - the new admin signs in and is forced to change the password
- [X] T022 [P] [US1] Playwright `e2e/tests/accounts-acceptance.spec.ts` part 1 (quickstart A, A2):
  - the main admin adds «أدمن تجريبي» with synthetic phone `07700000101` and only «إدارة المسوّقين»
  - in a new context the admin signs in and changes the password
  - the menu has المسوّقون and lacks الإعدادات and الأدمنية والصلاحيات
  - `/admin/settings` redirects to `/admin`

### Implementation for User Story 1

- [X] T023 [US1] Create the router `api/app/api/admins.py`: `GET /admin/admins` and `POST /admin/admins` with `require_roles("super_admin")`, calling `account_service.create_account(role="admin")`. Register it in `api/app/main.py`
- [X] T024 [US1] Create the page `web/src/pages/admin/Admins.tsx`, replacing the `AdminAdmins` placeholder in `web/src/pages/admin/placeholders.tsx` and `web/src/router.tsx` (contracts/ui-routes.md › "/admin/admins"):
  - the main-admin row first with «كل الصلاحيات» and no actions
  - admin rows with permission chips and the state chip
  - the «إضافة أدمن» dialog built from `AccountDialog` + `PermissionSwitches`, all off by default
  - cards on a phone, a table from `md` up; server errors shown inline in Arabic

**Checkpoint**: The main admin can create permission-limited admins, and they see the right menu.

---

## Phase 4: User Story 2 - Admin with `marketers` permission manages marketers (Priority: P1)

**Goal**: A holder of `marketers` lists, adds, edits, deactivates, reactivates, and resets marketers.

**Independent Test**: As the `marketers`-only admin, add a marketer, deactivate them while they are signed in (their next action shows «الحساب موقوف، راجع الإدارة»), reactivate them, and reset the password (forced change).

### Tests for User Story 2

- [X] T025 [P] [US2] Integration tests in `api/tests/integration/test_marketers.py` for every route in contracts/api.md › "Marketers":
  - an admin with `marketers` and super_admin pass; an admin without it and a marketer → 403
  - an admin id or the super_admin id on `/marketers/{id}*` → 404 (FR-012)
  - sending `permissions` → 422
  - a phone edit to a taken phone → 409; keeping the same phone is allowed
  - a phone edit does **not** end the marketer's sessions: the old access token still works, and the next login works with the new phone and fails with the old one
  - deactivate → that marketer's existing access token gets 403 `account_inactive` and login is refused
  - reactivate → login works with the old password
  - reset → old sessions get 401 and the next login has `must_change_password`
  - audit entries are correct, with none on no-ops
- [X] T026 [P] [US2] Playwright, in `e2e/tests/accounts-acceptance.spec.ts` part 2 (quickstart A3): the `marketers` admin adds «مسوّق تجريبي» with synthetic phone `07700000201`, and the marketer signs in on the Pixel 7 profile and is forced to change the password. Separately, `e2e/tests/deactivation.spec.ts` (quickstart D, E, F) is self-contained: in `beforeAll` it creates its own synthetic `marketers` admin and marketer through the API as the main admin (helper in `e2e/tests/helpers.ts`), then deactivates while the marketer is signed in, reactivates, and resets. It does not depend on the US1 UI

### Implementation for User Story 2

- [X] T027 [US2] Create the router `api/app/api/marketers.py`: GET, POST, PATCH `{id}`, and POST `{id}/deactivate|reactivate|reset-password` with `require_permission("marketers")`, using `account_service.get_target(role="marketer")`. Register it in `api/app/main.py`
- [X] T028 [US2] Create the page `web/src/pages/admin/Marketers.tsx`, replacing the `AdminMarketers` placeholder (contracts/ui-routes.md › "/admin/marketers"):
  - client-side search by name or phone, and the filter الكل / فعّال / موقوف
  - add and edit through `AccountDialog`
  - «تصفير كلمة السر» through `ResetPasswordDialog`
  - «إيقاف» with `ConfirmDialog`, and «إعادة تفعيل»
  - snackbar «تم الحفظ»; the temporary password is never shown again

**Checkpoint**: The acceptance criterion of the feature is met: US1 and US2 together.

**Batch 1 notes (2026-11-22)**:
- T016: implemented as `refreshUser()` in `AuthProvider` (dedup'd `/api/auth/me` call) instead of a TanStack query. It runs on every route change in `AdminLayout` and `MarketerLayout`, on window focus, and after any `forbidden`. Same behaviour, less code.
- Found by e2e T026: a deactivated user saw a bare sign-in screen, because deactivation also revokes the sessions and the server answered `session_revoked` first. `deps.current_user_allow_password_change` and `auth_service.refresh` now check `is_active` before session validity, so the user gets «الحساب موقوف، راجع الإدارة» (FR-015). Covered in `test_marketers.py`.
- `MarketerLayout` also re-reads the user on navigation, so a deactivation or reset reaches a marketer on the next tap even on placeholder pages.
- e2e: `workers: 1` in `e2e/playwright.config.ts` so `admin-first-login` (which sets the main admin password) runs before the 002 specs; acceptance spec named `admins-acceptance.spec.ts` to sort after it.

---

## Phase 5: User Story 3 - Main admin edits an admin's permissions or deactivates them (Priority: P2)

**Goal**: The main admin edits an admin's name, phone, and permissions, deactivates or reactivates them, and resets their password. The changes apply on the admin's next request.

**Independent Test**: Turn `settings` on for the signed-in `marketers` admin; their next navigation shows الإعدادات. Turn it off; the page is gone and the API returns 403. Deactivate them; their next action signs them out.

### Tests for User Story 3

- [ ] T029 [P] [US3] Integration tests in `api/tests/integration/test_admins_manage.py`:
  - PATCH permissions → the admin's existing token is evaluated with the new list on the next request; `user.permissions_changed` audit with before/after
  - PATCH name and permissions together → two audit entries
  - deactivate, reactivate, and reset, as in US2 but for admins
  - every action targeting the super_admin id → 404, with no data change (SC-004)
  - an admin with `marketers` calling these → 403
- [ ] T030 [P] [US3] Playwright `e2e/tests/permission-change.spec.ts` (quickstart B, G):
  - toggle الإعدادات for the signed-in admin; the menu updates on navigation without signing out
  - the main-admin row has no actions

### Implementation for User Story 3

- [ ] T031 [US3] Add to `api/app/api/admins.py`: `PATCH /admin/admins/{id}` and `POST /admin/admins/{id}/deactivate|reactivate|reset-password` with `require_roles("super_admin")`. They use `account_service.get_target(role="admin")` and call `ensure_not_protected` before every change
- [ ] T032 [US3] Add the actions to `web/src/pages/admin/Admins.tsx`:
  - «تعديل»: `AccountDialog` without the password field, with `PermissionSwitches`
  - «تصفير كلمة السر» with the explanation text
  - «إيقاف» with `ConfirmDialog`, and «إعادة تفعيل»
  - refresh the list after each action

**Checkpoint**: Admins can be fully managed. The main admin stays protected.

---

## Phase 6: User Story 4 - «حسابي» page for every user (Priority: P2)

**Goal**: Name, phone, and role are read-only for everyone. The password change requires the current password. The main admin can edit their own name.

**Independent Test**: Open «حسابي» as each of the three roles. Only the main admin has «تعديل الاسم»; the new name shows in the top bar and in the audit log.

### Tests for User Story 4

- [ ] T033 [P] [US4] Integration tests in `api/tests/integration/test_me_name.py`:
  - `PATCH /api/auth/me {name}` as super_admin → 200 with a `user.updated` audit entry (actor = target)
  - as an admin or a marketer → 403
  - a body with `phone` → 422; a name outside 2–100 → 422
- [ ] T034 [P] [US4] Vitest `web/src/__tests__/account-panel.test.tsx`: the name and phone have no editable input for marketer and admin; the «تعديل الاسم» button shows only for super_admin

### Implementation for User Story 4

- [ ] T035 [US4] Add `PATCH /me` to `api/app/api/auth.py`, using `NameUpdate` and `account_service.update_account(name=...)` and allowed only for `super_admin` (research.md R7, data-model.md › `users.name`)
- [ ] T036 [US4] Update `web/src/pages/AccountPanel.tsx` (contracts/ui-routes.md › "حسابي"):
  - fields read-only
  - for super_admin, an «تعديل الاسم» dialog that invalidates `['me']` after saving so the top bar updates
  - keep «تغيير كلمة السر» and «تسجيل الخروج»

**Checkpoint**: «حسابي» matches system.md §3.5.

---

## Phase 7: User Story 5 - Every account action is recorded, and the main admin views the log (Priority: P2)

**Goal**: The main admin has a read-only «سجل العمليات», newest first, with date and actor filters and before/after values.

**Independent Test**: After running US1–US4 actions, filter the log by today and by «أدمن تجريبي». The entries are correct and contain no password data. Any other account gets 403.

### Tests for User Story 5

- [ ] T037 [P] [US5] Integration tests in `api/tests/integration/test_audit_viewer.py`:
  - `GET /api/admin/audit`: newest first, keyset `before_id`/`has_more`/`next_before_id`, `limit` max 100
  - the `from`/`to` Baghdad-day boundaries: an entry at 23:30 Baghdad belongs to that day
  - `actor_id` (including `system`); actor and target names joined
  - `GET /api/admin/audit/actors`
  - an admin with all permissions and a marketer → 403
  - no write or delete route exists (405 or 404)
- [ ] T038 [P] [US5] Test in `api/tests/integration/test_audit_completeness.py` (SC-005): run every action of FR-019 once and assert exactly one matching entry per kind of change (a combined name+permissions PATCH → two entries). Scan all `before`/`after` JSON for the temporary passwords used and for the keys `password`, `hash`, and `token`

### Implementation for User Story 5

- [ ] T039 [P] [US5] Create `api/app/schemas/audit.py` (`AuditEntryOut`, `AuditPage`, `ActorOut`) and `api/app/services/audit_query.py`: a filtered keyset query using `baghdad_day_bounds` and the actor index, joining actor and target users
- [ ] T040 [US5] Create the router `api/app/api/audit.py`: `GET /admin/audit` and `GET /admin/audit/actors` with `require_roles("super_admin")`. Register it in `api/app/main.py`. Depends on T039
- [ ] T041 [P] [US5] Add typed calls in `web/src/lib/audit.ts`
- [ ] T042 [US5] Create the page `web/src/pages/admin/Audit.tsx`, replacing the `AdminAudit` placeholder (contracts/ui-routes.md › "/admin/audit"):
  - the filters من تاريخ / إلى تاريخ / المنفّذ (plus «النظام») and «مسح الفلاتر»
  - entries with `formatBaghdad`, the Arabic labels from `web/src/lib/labels.ts`, and قبل/بعد lists (permissions shown by label, booleans as نعم/لا)
  - for `user.created`, show the role next to the label, e.g. «إنشاء حساب (مسوّق)» / «إنشاء حساب (أدمن)» (fix I3)
  - «تحميل المزيد» and the empty state «لا توجد عمليات»; no edit controls

**Checkpoint**: All five stories work independently.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T043 [P] Update `README.md` (the feature list) and `specs/001-project-skeleton-auth/contracts/ui-routes.md` with a note that the admin route access is replaced by `specs/002-accounts-permissions/contracts/ui-routes.md`
- [ ] T044 [P] Check that the log redaction filter in `api/app/logging_config.py` covers `temporary_password`. Add a case to `api/tests/integration/test_log_safety.py`
- [ ] T045 Run `scripts/test-all.sh` (ruff, pytest, eslint, typecheck, vitest, e2e) and fix any failures
- [ ] T046 Run `docker compose up --build`, walk quickstart.md scenarios A–J manually, then write the Arabic manual-test steps to `specs/002-accounts-permissions/manual-test-ar.md` (CLAUDE.md). Include timed checks for SC-006 (add a marketer from a phone in under 1 minute) and SC-008 (find an entry by date and actor in under 30 seconds)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: needs Setup. It blocks every story. Inside it: T008 comes before T014; T009 and T011 come before T012; T013 comes before T014; T015 comes before T017 and T018.
- **US1 (Phase 3)**: needs Foundational.
- **US2 (Phase 4)**: needs Foundational. The service is shared, so the API is independent of US1. Only the acceptance e2e (`accounts-acceptance.spec.ts` part 2) continues the US1 flow; `deactivation.spec.ts` seeds its own accounts through the API, so US2 is testable alone.
- **US3 (Phase 5)**: needs US1 (it extends `admins.py` and `Admins.tsx`).
- **US4 (Phase 6)**: needs Foundational only.
- **US5 (Phase 7)**: needs Foundational. T038 needs the routes of US1–US4.
- **Polish (Phase 8)**: needs every story.

### Within Each Story

Tests first (they must fail), then the router or service, then the page. Commit after each story checkpoint.

### Parallel Opportunities

- T001 and T002 can run together.
- In Phase 2, T003–T007 (tests) can run together, then T009, T010, T011, T013, T015, T019, and T020.
- After Phase 2, US1, US2, US4, and US5 (except T038) can proceed in parallel. US3 follows US1.

## Parallel Example: User Story 2

```bash
Task: "T025 Integration tests in api/tests/integration/test_marketers.py"
Task: "T026 Playwright accounts-acceptance part 2 + deactivation.spec.ts"
# then
Task: "T027 Router api/app/api/marketers.py"
Task: "T028 Page web/src/pages/admin/Marketers.tsx"
```

---

## Implementation Strategy

### MVP (acceptance criterion)

1. Phase 1 and Phase 2.
2. Phase 3 (US1) and Phase 4 (US2). Together they meet the acceptance criterion: the main admin adds a `marketers`-only admin, that admin adds a marketer and does not see الإعدادات.
3. **STOP and VALIDATE** with quickstart A–A3 and D–F.

### Incremental Delivery

4. US3: managing admins.
5. US4: «حسابي».
6. US5: the audit viewer.
7. Polish: full test gate, `docker compose up`, and the Arabic manual steps.

## Notes

- Use synthetic names and phones only (`07700000xxx`) in tests and e2e. Never use real data (CLAUDE.md).
- Temporary passwords never appear in logs, audit entries, responses, or the UI after submit.
- No delete route or button for accounts or audit entries exists anywhere.
