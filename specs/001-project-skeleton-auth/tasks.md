---

description: "Task list for feature 001 — Project Skeleton & Sign-In"
---

# Tasks: Project Skeleton & Sign-In

**Input**: Design documents from `specs/001-project-skeleton-auth/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md),
[contracts/ui-routes.md](./contracts/ui-routes.md), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. Constitution Principle VIII requires pytest for every business rule and
Playwright for critical flows, and the owner asked for full `normalize_phone` tests. In each story,
write the test tasks first and confirm they fail before implementing.

**Organization**: Tasks are grouped by user story (spec.md US1–US6) so each can be implemented and
tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US6); Setup, Foundational, and Polish have none
- Paths follow the monorepo in plan.md: `api/`, `web/`, `e2e/`, `deploy/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository skeleton, tooling, containers

- [X] T001 Create the monorepo directories from plan.md (`api/app/{core,models,schemas,services,api}`, `api/tests/{unit,integration,fixtures}`, `api/migrations/versions`, `web/src`, `web/public/icons`, `e2e/tests`, `deploy/`) and a root `.gitignore` that ignores `.env`, `node_modules`, `__pycache__`, `dist`, and Playwright reports
- [X] T002 Initialize the Python 3.12 project in `api/pyproject.toml` with FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pydantic-settings, psycopg[binary] 3, PyJWT, argon2-cffi, and uvicorn (pinned latest stable); dev deps pytest, httpx, and ruff, with ruff and pytest config in the same file
- [X] T003 [P] Initialize the Vite React 18 + TypeScript app in `web/package.json`, `web/tsconfig.json`, and `web/vite.config.ts` with react-router-dom, @tanstack/react-query, @mui/material, @mui/icons-material, @emotion/react, @emotion/styled, @emotion/cache, stylis, stylis-plugin-rtl, @fontsource/cairo, and vite-plugin-pwa; dev deps vitest, @testing-library/react, jsdom, eslint, and prettier; scripts `dev`, `build`, `test`, `lint`
- [X] T004 [P] Initialize Playwright in `e2e/package.json` and `e2e/playwright.config.ts` with projects `desktop-chrome`, `pixel-7`, and `iphone-14`; `baseURL` from env `E2E_BASE_URL` (default `https://proxy`, `ignoreHTTPSErrors: true`)
- [X] T005 [P] Create `.env.example` with every variable listed in the plan.md "Environment variables" table, with comments in English and synthetic example values only (Principle II / CLAUDE.md)
- [X] T006 [P] Create `api/Dockerfile` (python:3.12-slim, non-root user, installs the project) and `api/entrypoint.sh` (`alembic upgrade head` → `python -m app.cli bootstrap` → `uvicorn app.main:app`), per research.md R7/R13
- [X] T007 [P] Create `web/Dockerfile`: a multi-stage build where `npm ci && npm run build` feeds a `caddy:2-alpine` runtime that serves `dist/` with SPA fallback to `index.html` (`web/Caddyfile`)
- [X] T008 [P] Create `deploy/Caddyfile` for `{$SITE_ADDRESS}`: route `/api/*` to `api:8000` and everything else to `web:80`; add the security headers from research.md R13 (HSTS, nosniff, Referrer-Policy, CSP self) and pass `X-Forwarded-For`
- [X] T009 Create `docker-compose.yml` with services `db` (postgres:16-alpine, volume `pgdata`, healthcheck), `api` (depends on healthy db, healthcheck `GET /api/health`), `web`, and `proxy` (only published ports 80/443, volumes `caddy_data`/`caddy_config`); all config from `.env`. `APP_ENV` defaults to `production` (`${APP_ENV:-production}`). This base file is the production/staging definition and MUST work alone with `docker compose -f docker-compose.yml up -d` (no dev settings in it)
- [X] T010 Create `docker-compose.override.yml` for development: mount `api/` with `uvicorn --reload`; run the `web` Vite dev server with HMR proxied through Caddy (WebSocket); set `APP_ENV=development` explicitly (the only place development mode is enabled)
- [X] T011 [P] Create the e2e overlay `docker-compose.e2e.yml` (`APP_ENV=test`, `SITE_ADDRESS=proxy` with Caddy `tls internal`, the `e2e` Playwright service) and `scripts/e2e.sh` + `scripts/e2e.ps1`. Each run starts an isolated project (`docker compose -p sijil-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build`) on a fresh DB volume, runs `python -m app.cli seed-demo --e2e`, runs Playwright, then always runs `down -v`. Every e2e run therefore starts from the same known state

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core backend and frontend infrastructure that all stories need, including base
sign-in/refresh/me

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational (write first, must fail)

- [X] T012 [P] Create the shared phone fixture `api/tests/fixtures/phone_cases.json` with every valid and invalid case listed in research.md R6 (including U+202A/U+202C, U+200F, spaces, dashes, `+964`, `00964`, `964`, missing leading 0, and Arabic-Indic and Persian digits) and the expected normalized output (`null` for invalid)
- [X] T013 [P] Unit tests for `normalize_phone` driven by the fixture in `api/tests/unit/test_phone.py`
- [X] T014 [P] Unit tests in `api/tests/unit/test_security.py` for Argon2id hash/verify/needs-rehash, access-token encode/decode with `sub`/`sid`/exp (15 min), expired and tampered tokens rejected, and refresh-token generation plus SHA-256 hashing
- [X] T015 [P] Unit tests in `api/tests/unit/test_timeutil.py` for `utc_now()` (overridable by the `frozen_clock` fixture), (tz-aware UTC) and `baghdad_month_bounds()` (month start/end in Asia/Baghdad returned as UTC, including the instant just before Baghdad midnight on the 1st)
- [X] T016 [P] Test fixtures in `api/tests/conftest.py`: create the `sijil_test` database from `TEST_DATABASE_URL`, run Alembic migrations once, wrap each test in a rolled-back transaction, provide a `TestClient`, and add a `make_user(role, ...)` factory that uses synthetic names and phones only, and a `frozen_clock` fixture that sets and advances the time returned by `app.core.timeutil.utc_now()` (DB `now()` is constant inside a test transaction, so logic must never depend on it)
- [X] T017 [P] Integration tests in `api/tests/integration/test_login.py` for `POST /api/auth/login`, `POST /api/auth/refresh`, and `GET /api/auth/me` per contracts/api.md. Cover: success body shape; the refresh cookie attributes (HttpOnly, Secure, SameSite=Strict, Path=/api/auth); a phone in `+964…` and Arabic-digit formats signs in; an invalid phone returns 422 `invalid_phone`; a wrong password and an unknown phone return the identical 401 `invalid_credentials`; an inactive account returns 403 `account_inactive`; refresh rotates the cookie; `/me` without a token returns 401
- [X] T018 [P] Vitest tests in `web/src/__tests__/phone.test.ts` for the TS `normalizePhone` mirror, using a copy of `phone_cases.json` (`web/src/__tests__/fixtures/phone_cases.json`)

### Implementation for Foundational

- [X] T019 Implement settings in `api/app/config.py` (pydantic-settings, every variable from `.env.example`); `APP_ENV` is one of `development`, `test`, `staging`, `production`. When `APP_ENV` is `staging` or `production`, refuse to start if `JWT_SECRET` or a password still equals `change-me` or `COOKIE_SECURE` is false
- [X] T020 Implement the engine and `get_db` session dependency in `api/app/db.py` (sync SQLAlchemy 2 + psycopg 3)
- [X] T021 [P] Implement `normalize_phone` in `api/app/core/phone.py` per research.md R6; the output satisfies data-model.md `users.phone` format
- [X] T022 [P] Implement `api/app/core/security.py`: Argon2id `hash_password`/`verify_password`/`needs_rehash` for data-model.md `users.password_hash`; a constant dummy hash for timing-safe unknown-phone checks; JWT `create_access_token(user_id, session_id)`/`decode_access_token`; `new_refresh_token()` plus `hash_refresh_token()` for data-model.md `sessions.refresh_token_hash`
- [X] T023 [P] Implement `api/app/core/timeutil.py` with `utc_now()` and `baghdad_month_bounds()` (Principle X). `utc_now()` is the single clock: every time used in logic (lock expiry, session expiry, token issue, timestamps written by services) comes from it, and its override hook is used only by tests
- [X] T024 [P] Create the `User` model in `api/app/models/user.py` with every column, type, default, and CHECK from data-model.md `users` (`users.name`, `users.phone` unique + CHECK `^07\d{9}$`, `users.password_hash`, `users.role` CHECK enum, `users.permissions` jsonb default `[]`, `users.is_active`, `users.must_change_password`, `users.failed_logins`, `users.locked_until`, `users.created_at`, `users.updated_at`) and the partial index on `role`
- [X] T025 [P] Create the `Session` model in `api/app/models/session.py` per data-model.md `sessions` (`sessions.id` uuid, `sessions.user_id` FK + index, `sessions.refresh_token_hash` unique, `sessions.previous_token_hash`, `sessions.created_at`, `sessions.last_used_at`, `sessions.expires_at`, `sessions.revoked_at`, `sessions.revoke_reason` values, `sessions.user_agent` truncated to 255)
- [X] T026 [P] Create the `AuditLog` model in `api/app/models/audit.py` per data-model.md `audit_log` (`audit_log.actor_id` nullable FK, `audit_log.action`, `audit_log.entity_type`, `audit_log.entity_id`, `audit_log.before`, `audit_log.after`, `audit_log.created_at` index desc)
- [X] T027 Create the Alembic environment (`api/alembic.ini`, `api/migrations/env.py`) and migration `api/migrations/versions/0001_users_sessions_audit.py` creating the three tables with all constraints from data-model.md (depends on T024–T026)
- [X] T028 Implement `api/app/services/audit_service.py` `record(db, actor_id, action, entity_type, entity_id, before, after)` with an allow-list serializer that drops `password_hash`, any token, and any OTP field from `audit_log.before`/`audit_log.after` (data-model.md); append-only, with no update or delete functions
- [X] T029 Implement error handling in `api/app/errors.py`: an `AppError(code, message, status, headers)` and handlers that return `{code, message}` with Arabic messages; validation errors map to a generic Arabic message without echoing input
- [X] T030 Implement logging in `api/app/logging_config.py` (not `logging.py`, to avoid shadowing the stdlib module): structured JSON logs; a redaction filter for `password`, `token`, `authorization`, `cookie`, and `refresh`; request bodies never logged
- [X] T031 Implement `api/app/services/auth_service.py` base sign-in. Normalize the phone (422 `invalid_phone`). Load the user with `SELECT … FOR UPDATE`. Verify the password, using the dummy hash for an unknown phone. On wrong password or unknown phone return 401 `invalid_credentials`. If the user is inactive (data-model.md `users.is_active`) return 403 `account_inactive`. On success reset data-model.md `users.failed_logins` and rehash if needed. Create a `sessions` row with `sessions.expires_at` = now + `REFRESH_TOKEN_DAYS`. Return tokens. Also implement `refresh(token)`: rotate data-model.md `sessions.refresh_token_hash` and slide `sessions.expires_at`/`sessions.last_used_at`; on an unknown, expired, or revoked token return 401 `session_revoked`
- [X] T032 Implement `api/app/api/deps.py`. `current_user` decodes the token (401 `token_expired`/`not_authenticated`), loads the user joined with the session from `sid`, and rejects with 401 `session_revoked` or 403 `account_inactive`. It rejects with 403 `password_change_required` when data-model.md `users.must_change_password` is true, unless the route uses the `allow_password_change` variant. Also add `require_roles(*roles)`, which returns 403 `forbidden`
- [X] T033 Implement the Pydantic v2 schemas in `api/app/schemas/auth.py` (`LoginRequest`, `TokenResponse`, `ChangePasswordRequest`) and `api/app/schemas/user.py` (`UserOut`: id, name, phone, role, permissions, must_change_password) per contracts/api.md, then the `api/app/api/auth.py` router: `POST /api/auth/login` and `POST /api/auth/refresh` set the `sijil_refresh` cookie per contracts/api.md (`COOKIE_SECURE` from settings); `GET /api/auth/me` uses `allow_password_change`
- [X] T034 [P] Implement `api/app/api/health.py` `GET /api/health` (DB `SELECT 1`, no version info)
- [X] T035 Wire `api/app/main.py`: app factory, the `/api` routers (auth, health), error handlers, logging, and trusted-proxy handling for `X-Forwarded-For` from `TRUSTED_PROXY_CIDRS`
- [X] T036 [P] Implement `web/src/lib/phone.ts` `normalizePhone` mirroring research.md R6 (client hint only)
- [X] T037 [P] Implement the RTL theme in `web/src/theme/index.ts` and `web/src/theme/RtlProvider.tsx`: an emotion cache with key `muirtl` and `stylis-plugin-rtl`, an MUI theme with `direction: 'rtl'` and the Cairo font (import `@fontsource/cairo` 400/600/700), and `<html lang="ar" dir="rtl">` in `web/index.html`
- [X] T038 [P] Implement `web/src/lib/time.ts` to format UTC ISO strings with `Intl.DateTimeFormat('ar-IQ', { timeZone: 'Asia/Baghdad' })`
- [X] T039 Implement the API client in `web/src/lib/api.ts`: a fetch wrapper with `credentials: 'same-origin'` and a Bearer header from the in-memory token; on 401 `token_expired`, call `/api/auth/refresh` once and retry; map network errors and timeouts to the Arabic «تعذّر الاتصال، حاول مرة أخرى» (FR-021); throw `{code, message}` errors
- [X] T040 Implement `web/src/auth/AuthProvider.tsx`: on start call `POST /api/auth/refresh` and then `GET /api/auth/me`; hold the access token in memory only (never localStorage) and expose `user`, `login()`, `logout()`, and `setSession()`; on 403 `account_inactive`, clear state and show «الحساب موقوف، راجع الإدارة»
- [X] T041 Implement the guards in `web/src/auth/guards.tsx`: `RequireAuth` (to `/login`), `RequireRole(roles)` (redirects to the role landing page from data-model.md "Role → landing page"), and `MustChangePasswordGate` (to `/change-password`)
- [X] T042 Implement `web/src/pages/Login.tsx` per contracts/ui-routes.md: phone and password fields, inline «رقم غير صالح» from `normalizePhone`, server messages shown verbatim, and redirect to the role landing page after sign-in
- [X] T043 Implement `web/src/router.tsx`, `web/src/App.tsx`, and `web/src/main.tsx`: QueryClientProvider, RtlProvider, AuthProvider, and the route table from contracts/ui-routes.md with placeholder elements for later stories

**Checkpoint**: `docker compose up` serves the login page in RTL Arabic. Tests T013–T018 pass.

---

## Phase 3: User Story 1 - Main admin signs in for the first time (Priority: P1) 🎯 MVP

**Goal**: The bootstrap super admin is created from the environment, signs in on desktop, is
forced to change the password, and reaches the admin panel with the §10 page list.

**Independent Test**: Start on an empty DB with `SUPERADMIN_*` set, sign in from desktop, change
the password, and see the right sidebar with 11 pages and «أدمن رئيسي».

### Tests for User Story 1 (write first, must fail)

- [X] T044 [P] [US1] Integration tests in `api/tests/integration/test_bootstrap.py`: an empty DB creates one `super_admin` with a normalized phone and `must_change_password=true` plus audit `user.bootstrap_created` with `actor_id` null; a second run with different env values creates or modifies nothing; missing or invalid env with no super admin exits non-zero, and captured output does not contain the password; with an existing super admin, missing env is ignored
- [X] T045 [P] [US1] Integration tests in `api/tests/integration/test_change_password.py` (forced path): a user with `must_change_password` gets 403 `password_change_required` on `/api/admin/ping` but 200 on `/api/auth/me`; change-password with the correct current password returns new tokens, clears the flag, and writes audit `user.password_changed` without password data; afterwards `/api/admin/ping` returns 200
- [X] T046 [P] [US1] Integration tests in `api/tests/integration/test_roles.py` (admin side): `super_admin` and `admin` get 200 on `GET /api/admin/ping`; a request without a token gets 401
- [X] T047 [P] [US1] Playwright test `e2e/tests/admin-first-login.spec.ts` (desktop-chrome project only; relies on the fresh stack from `scripts/e2e.sh`): sign in with the bootstrap admin using the `+964` format, land on `/change-password`, save, land on `/admin`, and see the sidebar on the right with the 11 §10 labels in order and «أدمن رئيسي» in the top bar

### Implementation for User Story 1

- [X] T048 [US1] Implement `python -m app.cli bootstrap` in `api/app/cli.py` per research.md R7: an advisory lock; create the super admin only if none exists; validate the phone with `normalize_phone` and the name length per data-model.md `users.name`; set data-model.md `users.must_change_password` true; audit `user.bootstrap_created`; never print the password
- [X] T049 [US1] Implement `change_password(user, session, current, new)` in `api/app/services/auth_service.py`: 400 `wrong_current_password`; 422 `weak_password` (fewer than 8 chars); 422 `same_password`; hash into data-model.md `users.password_hash`; clear `users.must_change_password`; update `users.updated_at`; revoke the user's other sessions with data-model.md `sessions.revoke_reason` `password_changed`; rotate the current session; audit `user.password_changed`
- [X] T050 [US1] Add `POST /api/auth/change-password` (`allow_password_change`) to `api/app/api/auth.py`, returning a new token body and cookie per contracts/api.md
- [X] T051 [P] [US1] Implement the `api/app/api/admin.py` router `GET /api/admin/ping` with `require_roles('super_admin','admin')` and register it in `api/app/main.py`
- [X] T052 [P] [US1] Implement `web/src/pages/ChangePassword.tsx`: current, new, and confirm fields; client-side checks (≥ 8 chars, match, differs) with Arabic messages; on success call `setSession()` and go to the role landing page
- [X] T053 [US1] Implement `web/src/layouts/AdminLayout.tsx`: from `md` up, a permanent right Drawer listing the 11 §10 pages in order and a top bar with the user name and role label; below `md`, an AppBar with a menu button opening the Drawer. «الأدمنية والصلاحيات» appears only for `super_admin`
- [X] T054 [US1] Implement the admin placeholder pages in `web/src/pages/admin/` (Home, Pending, AwaitingLink, Subscribers, Marketers, Settings, Admins, Reports, Import, Backup, Audit, Account) per contracts/ui-routes.md, each an empty state with its Arabic title. `Admins` is wrapped in `RequireRole(['super_admin'])`. `Account` shows the name, role, a change-password link, and sign-out
- [X] T055 [US1] Wire the `/admin/*` routes under `RequireAuth` + `MustChangePasswordGate` + `RequireRole(['super_admin','admin'])` with `AdminLayout` in `web/src/router.tsx`

**Checkpoint**: US1 is fully functional. The main admin signs in from a computer and sees the
admin panel.

---

## Phase 4: User Story 2 - Marketer signs in from a phone and sees the dashboard (Priority: P1)

**Goal**: A synthetic test marketer signs in on a phone and sees the dashboard skeleton with the
bottom bar.

**Independent Test**: Run `seed-demo`, sign in in the Pixel 7 and iPhone 14 viewports, and see the
two disabled buttons, «تم الربط هذا الشهر: 0», and the 4-icon bottom bar. `/admin` is refused.

### Tests for User Story 2 (write first, must fail)

- [X] T056 [P] [US2] Integration tests in `api/tests/integration/test_roles.py` (marketer side): a marketer gets 403 `forbidden` on `GET /api/admin/ping`; a marketer gets 200 on `GET /api/marketer/dashboard` with `linked_this_month = 0` and an Arabic `month_label` for the current Baghdad month; an admin and a super admin get 403 on the marketer dashboard
- [X] T057 [P] [US2] Integration test in `api/tests/integration/test_seed_demo.py`: `seed-demo` creates the synthetic marketer idempotently and is allowed in `development`, `test`, and `staging`; it refuses with a non-zero exit when `APP_ENV=production`; `--e2e` also creates the lockout account `07700000002` and the flagged account `07700000003` (`must_change_password` true)
- [X] T058 [P] [US2] Playwright test `e2e/tests/marketer-mobile.spec.ts` (pixel-7 and iphone-14): sign in as the demo marketer; the dashboard shows the two disabled buttons and «تم الربط هذا الشهر: 0», and the bottom bar shows الرئيسية، الطلبات، الإشعارات، حسابي; navigating to `/admin` redirects to `/`; in desktop-chrome the marketer sees the right sidebar and «مسوّق» in the top bar

### Implementation for User Story 2

- [X] T059 [US2] Implement `python -m app.cli seed-demo` in `api/app/cli.py` per research.md R8: refuse when `APP_ENV=production` (allowed in development, test, and staging); idempotently create «مسوّق تجريبي» `07700000001` (role `marketer` per data-model.md `users.role`, `users.permissions` `[]`) with the password from `DEMO_MARKETER_PASSWORD`. With `--e2e`, also create «مسوّق قفل» `07700000002` and «مسوّق تغيير» `07700000003`, the latter with data-model.md `users.must_change_password` true. All names and phones are synthetic
- [X] T060 [P] [US2] Implement the `api/app/api/marketer.py` router `GET /api/marketer/dashboard` with `require_roles('marketer')`, returning a fixed `linked_this_month: 0` and an Arabic month label from `baghdad_month_bounds()`; register it in `api/app/main.py`
- [X] T061 [US2] Implement `web/src/layouts/MarketerLayout.tsx`: below `md`, a fixed MUI `BottomNavigation` with icons and labels (الرئيسية، الطلبات، الإشعارات، حسابي); from `md` up, a permanent right Drawer with the same items plus a top bar with the name and «مسوّق»
- [X] T062 [US2] Implement `web/src/pages/marketer/Dashboard.tsx`: a large disabled «إضافة مشترك جديد», a disabled «إضافة اشتراك لمشترك موجود» with caption «قريباً», and a counter card «تم الربط هذا الشهر: N» from `/api/marketer/dashboard` (TanStack Query) with an Arabic error and retry state
- [X] T063 [P] [US2] Implement `web/src/pages/marketer/Requests.tsx`, `Notifications.tsx`, and `Account.tsx`: empty states «قريباً»; Account shows the name, phone, role «مسوّق», a «تغيير كلمة السر» link, and «تسجيل الخروج»
- [X] T064 [US2] Wire the marketer routes (`/`, `/requests`, `/notifications`, `/account`) under `RequireAuth` + `MustChangePasswordGate` + `RequireRole(['marketer'])` with `MarketerLayout` in `web/src/router.tsx`

**Checkpoint**: US1 and US2 both work locally.

---

## Phase 5: Early Staging Deployment (acceptance on real devices)

**Purpose**: Make the feature reachable over real HTTPS at `https://sijil.t3cftth.net`, so the
acceptance criterion (main admin on a computer, marketer on a real phone) and PWA installation can
be verified. The server and the domain are ready.

- [ ] T065 Write `deploy/staging.md` (Arabic) covering: DNS check for `sijil.t3cftth.net`; ports 80/443 open; cloning the repo and checking out the feature branch; creating a server-only `.env` from `.env.example` with `SITE_ADDRESS=sijil.t3cftth.net`, `APP_ENV=staging`, `COOKIE_SECURE=true`, and freshly generated `JWT_SECRET`, `POSTGRES_PASSWORD`, `SUPERADMIN_PASSWORD`, `DEMO_MARKETER_PASSWORD` (never committed); and the production-only compose command. It also states that before go-live (feature 014) the demo accounts are deactivated (never deleted) and `APP_ENV` becomes `production`
- [ ] T066 Create `scripts/deploy-staging.sh`, run on the server: `git pull`; `docker compose -f docker-compose.yml up -d --build` (never the override file); wait until `https://sijil.t3cftth.net/api/health` returns ok; run `docker compose -f docker-compose.yml exec api python -m app.cli seed-demo`. Exit non-zero on any failure
- [ ] T067 Deploy to staging and run quickstart scenarios 3–10 at `https://sijil.t3cftth.net`: main admin from a computer; the demo marketer from a real Android phone and a real iPhone. Record the results in `specs/001-project-skeleton-auth/manual-test-ar.md`

**Checkpoint**: The feature's acceptance criterion is verified on real devices over HTTPS.

---

## Phase 6: User Story 3 - Session stays active until sign-out or deactivation (Priority: P2)

**Goal**: Persistent sessions with per-device sign-out, rotation reuse detection, and immediate
effect of deactivation.

**Independent Test**: Sign in, reopen the browser, and confirm still signed in; sign out and
confirm `/login`; set `is_active=false` and confirm the next action shows «الحساب موقوف، راجع
الإدارة».

### Tests for User Story 3 (write first, must fail)

- [X] T068 [P] [US3] Integration tests in `api/tests/integration/test_sessions.py`: logout revokes only the current session (a second device's refresh still works) and clears the cookie, returning 204 even when already signed out; presenting a rotated refresh token returns 401 `session_revoked` and revokes that session (`reuse_detected`); an expired session is refused; after `is_active=false` the existing access token gets 403 `account_inactive` on the next request and refresh is refused; a refresh 29 days after last use (via `frozen_clock`) still works and slides `expires_at`; `deactivate_user_sessions(user_id, reason)` revokes every session of that user with the given `revoke_reason`
- [X] T069 [P] [US3] Playwright test `e2e/tests/session.spec.ts`: sign in, open a new browser page in the same context, and confirm still signed in; «تسجيل الخروج» returns to `/login`; pressing back does not show protected content

### Implementation for User Story 3

- [X] T070 [US3] Add reuse detection to `refresh()` in `api/app/services/auth_service.py`: on rotation store the old hash in data-model.md `sessions.previous_token_hash`; a match on it revokes the session with `sessions.revoke_reason` `reuse_detected`
- [X] T071 [US3] Implement `logout(refresh_token)` in `api/app/services/auth_service.py` (sets data-model.md `sessions.revoked_at` and `sessions.revoke_reason` `logout`) and `POST /api/auth/logout` in `api/app/api/auth.py` (always 204, clears the cookie)
- [X] T072 [US3] Add `deactivate_user_sessions(user_id, reason)` to `api/app/services/auth_service.py` (revokes all sessions; feature 002 calls it on deactivation and password reset). Its test is in T068
- [X] T073 [US3] Wire sign-out in `web/src/auth/AuthProvider.tsx` `logout()` (call the API, clear the in-memory token and the TanStack Query cache, navigate to `/login` with `replace`) and the «تسجيل الخروج» buttons in `web/src/pages/marketer/Account.tsx` and `web/src/pages/admin/Account.tsx`

**Checkpoint**: Sessions persist and end exactly as the spec requires.

---

## Phase 7: User Story 4 - Temporary lock after failed attempts (Priority: P2)

**Goal**: 5 consecutive failures lock the account for 15 minutes; a per-IP limiter blocks
spraying.

**Independent Test**: 5 wrong passwords, then the correct one, give 423 with the minutes
remaining; after the lock period sign-in works.

### Tests for User Story 4 (write first, must fail)

- [X] T074 [P] [US4] Integration tests in `api/tests/integration/test_lockout.py`: the 5th wrong attempt sets `locked_until` = now + 15 min and writes audit `user.locked`; while locked, the correct password gets 423 `account_locked` with `retry_after_seconds` and a `Retry-After` header; with a frozen or advanced clock, sign-in succeeds after expiry; a success after 3 failures resets the counter; an invalid phone format does not change any counter; the per-IP limiter returns 429 `too_many_attempts` after `LOGIN_IP_LIMIT` attempts
- [X] T075 [P] [US4] Playwright test `e2e/tests/lockout.spec.ts`: desktop-chrome project only, using the dedicated lockout account `07700000002` from `seed-demo --e2e`: 5 wrong passwords, then the Arabic lock message with minutes appears even with the correct password

### Implementation for User Story 4

- [X] T076 [US4] Add lockout to sign-in in `api/app/services/auth_service.py` per the data-model.md "Lockout state" diagram. Check data-model.md `users.locked_until` first and return 423 with the remaining minutes in Arabic. On a wrong password increment `users.failed_logins`; at `LOCKOUT_THRESHOLD`, set `users.locked_until` = now + `LOCKOUT_MINUTES`, reset the counter, and audit `user.locked`. All of this happens in the same row-locked transaction
- [X] T077 [P] [US4] Implement the per-IP sliding-window limiter in `api/app/core/ratelimit.py` (`LOGIN_IP_LIMIT` / `LOGIN_IP_WINDOW_MINUTES`, client IP from trusted `X-Forwarded-For`) and apply it to `POST /api/auth/login` in `api/app/api/auth.py` (429 `too_many_attempts`)
- [X] T078 [US4] Show the lock and 429 messages in `web/src/pages/Login.tsx` (server Arabic message; disable the submit button until `retry_after_seconds` elapses)

**Checkpoint**: Password guessing is blocked per account and per IP.

---

## Phase 8: User Story 5 - Forced password change after reset (Priority: P2)

**Goal**: Any flagged account is confined to `/change-password`, and any user can change the
password voluntarily from «حسابي».

**Independent Test**: Flag a synthetic marketer with `must_change_password`; after sign-in only
`/change-password` is reachable (UI and API); after saving, the dashboard opens. Voluntary change
from «حسابي» works.

### Tests for User Story 5 (write first, must fail)

- [X] T079 [P] [US5] Extend `api/tests/integration/test_change_password.py`: a flagged marketer gets 403 `password_change_required` on `/api/marketer/dashboard`; `weak_password`, `same_password`, and `wrong_current_password` cases; a voluntary change by an unflagged user works and revokes the other sessions; the audit row has no password or hash fields
- [X] T080 [P] [US5] Vitest test in `web/src/__tests__/guards.test.tsx`: `MustChangePasswordGate` redirects every route to `/change-password` while flagged; `RequireRole` sends a marketer from `/admin` to `/` and an admin from `/` to `/admin`
- [X] T081 [P] [US5] Playwright test `e2e/tests/forced-change.spec.ts` (pixel-7): pixel-7 project only: the flagged account `07700000003` from `seed-demo --e2e` is confined to `/change-password`, saves, and lands on the dashboard

### Implementation for User Story 5

- [X] T082 [US5] Make `web/src/pages/ChangePassword.tsx` work in voluntary mode: reachable from both Account pages; show a back link when not forced; on success remain signed in on this device

**Checkpoint**: Reset users cannot use the app until they set a new password.

---

## Phase 9: User Story 6 - Install Sijil on the phone (Priority: P3)

**Goal**: The installable PWA shows the name «سِجلّ» and the Sijil icon and launches full-screen.

**Independent Test**: "Add to Home Screen" on Android Chrome and iPhone Safari shows the icon and
name and opens standalone.

### Tests for User Story 6 (write first, must fail)

- [X] T083 [P] [US6] Playwright test `e2e/tests/pwa.spec.ts`: `/manifest.webmanifest` has `name` and `short_name` «سِجلّ», `lang: ar`, `dir: rtl`, `display: standalone`, and icons 192/512/maskable; `index.html` has `apple-touch-icon`, `apple-mobile-web-app-capable`, and the theme color; a service worker registers; requests to `/api/*` are not served from the SW cache

### Implementation for User Story 6

- [X] T084 [P] [US6] Create the placeholder Sijil icons `web/public/icons/icon-192.png`, `icon-512.png`, `icon-512-maskable.png`, and `apple-touch-icon.png` (180) plus `web/public/favicon.svg` (the letter «س» on the brand color)
- [X] T085 [US6] Configure `vite-plugin-pwa` in `web/vite.config.ts` per contracts/ui-routes.md "PWA manifest": `registerType: 'autoUpdate'`; Workbox precaches the app shell and fonts only, with `navigateFallbackDenylist: [/^\/api\//]` and no runtime caching for `/api/*`
- [X] T086 [US6] Add the iOS meta tags to `web/index.html` (`apple-touch-icon`, `apple-mobile-web-app-capable`, `apple-mobile-web-app-title` «سِجلّ», `theme-color`, viewport with `viewport-fit=cover`) and safe-area padding for the bottom bar in `web/src/layouts/MarketerLayout.tsx`

**Checkpoint**: All six stories work independently.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T087 [P] Write the Arabic `README.md`: what Sijil is; prerequisites; `cp .env.example .env`; `docker compose up --build`; `seed-demo`; how to run the tests (pytest, vitest, `scripts/e2e.sh`); how to deploy to staging (link to `deploy/staging.md`); how to trust the Caddy local certificate; how to open the app from a phone on the LAN
- [X] T088 [P] Add a log-safety test in `api/tests/integration/test_log_safety.py`: capture logs during login, a failed login, change-password, and bootstrap, and assert that no password, token, or cookie value appears
- [X] T089 [P] Add a test script `scripts/test-all.sh` (with a PowerShell equivalent `scripts/test-all.ps1`) that runs ruff, pytest, vitest, eslint, and the e2e run via `scripts/e2e.sh` and exits non-zero on any failure (the Principle VIII merge gate)
- [X] T090 Verify the web bundle size (app shell < 300 KB gzipped, excluding fonts) with `npm run build` and fix any oversized imports (e.g., MUI icons via per-icon imports)
- [ ] T091 (local part done 2026-11-22; staging part waits for Phase 5) Run every scenario in [quickstart.md](./quickstart.md) against local `docker compose up`, then redeploy to staging with `scripts/deploy-staging.sh` and repeat scenarios 3–11 there (scenario 11, PWA install on a real Android and iPhone, needs US6); fix gaps
- [X] T092 Write the Arabic manual test steps for the owner (per CLAUDE.md) in `specs/001-project-skeleton-auth/manual-test-ar.md`, completing the file started in Phase 5: desktop admin first sign-in, phone marketer sign-in, and PWA installation on Android and iPhone at `https://sijil.t3cftth.net`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none. T009 depends on T006–T008; T010 depends on T009.
- **Foundational (Phase 2)**: depends on Setup. T027 depends on T024–T026; T031 on T021, T022,
  T027, and T028; T032 on T022 and T031; T033 on T031 and T032; T035 on T033 and T034;
  T039–T043 run in order on the web side.
- **US1 (Phase 3)** and **US2 (Phase 4)**: both depend only on Foundational and are independent of
  each other (US2's Account change-password link works once US1's T052 exists; until then it is a
  disabled link).
- **US3, US4, US5**: depend on Foundational. US5 builds on US1's change-password endpoint and page
  (T049, T050, T052). US3's Account sign-out buttons need the Account pages from US1 (T054) and
  US2 (T063).
- **US6**: depends only on Setup and Foundational (web).
- **Staging (Phase 5)**: depends on US1 and US2. It is redeployed during Polish after US3–US6.
- **Polish**: after the desired stories.

### Within Each Story

Tests first (they fail), then models and migrations, then services, then endpoints, then the UI,
then wiring.

### Parallel Opportunities

- Setup: T003–T008 are in parallel after T001/T002.
- Foundational tests T012–T018 are all [P]; implementations T021–T026, T034, and T036–T038
  are [P].
- After Foundational, US1, US2, US4, and US6 can proceed in parallel; US3 and US5 follow US1/US2
  for their UI parts.

---

## Parallel Example: User Story 1

```bash
# Tests first, together:
Task: "Integration tests for bootstrap in api/tests/integration/test_bootstrap.py"
Task: "Integration tests for forced change in api/tests/integration/test_change_password.py"
Task: "Integration tests for admin roles in api/tests/integration/test_roles.py"
Task: "Playwright admin-first-login in e2e/tests/admin-first-login.spec.ts"

# Then independent implementation files together:
Task: "Admin ping router in api/app/api/admin.py"
Task: "ChangePassword page in web/src/pages/ChangePassword.tsx"
```

## Parallel Example: User Story 2

```bash
Task: "Marketer role tests in api/tests/integration/test_roles.py"
Task: "seed-demo tests in api/tests/integration/test_seed_demo.py"
Task: "Playwright marketer-mobile in e2e/tests/marketer-mobile.spec.ts"
Task: "Marketer dashboard router in api/app/api/marketer.py"
Task: "Requests/Notifications/Account placeholders in web/src/pages/marketer/"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 Setup, then Phase 2 Foundational.
2. Phase 3 (US1) and Phase 4 (US2). Together they are the feature's acceptance criterion: the main
   admin on a computer and the test marketer on a phone.
3. **STOP and VALIDATE** with quickstart scenarios 1–5 locally.
4. Phase 5: deploy to `https://sijil.t3cftth.net` and verify on a real computer, Android phone, and iPhone.

### Incremental Delivery

5. US3 sessions, then US4 lockout, then US5 forced change, then US6 PWA. Each is validated by its
   own tests.
6. Polish: README, log safety, the full test gate, quickstart, and the Arabic manual test steps.

---

## Notes

- Synthetic data only in tests, seeds, and examples (no real cards or subscribers).
- Never log or echo passwords, tokens, or cookies.
- Commit after each task or logical group on branch `001-project-skeleton-auth`.
