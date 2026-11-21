# Implementation Plan: Project Skeleton & Sign-In

**Branch**: `001-project-skeleton-auth` | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-project-skeleton-auth/spec.md`

## Summary

This feature sets up the Sijil monorepo (FastAPI backend in `api/`, React PWA in `web/`), Docker
Compose with `db`, `api`, `web`, and `proxy`, and phone + password sign-in for three roles. Phones
are normalized per §8.1, and the bootstrap main admin is created from the environment. Sessions
use a 15-minute in-memory JWT access token plus a rotating 30-day refresh token in an httpOnly
SameSite=Strict cookie, backed by a `sessions` table. That table enables per-device sign-out and
immediate revocation on deactivation or password change. Accounts lock for 15 minutes after 5
failures, and a flagged account must change its password. The Arabic RTL shell has a marketer
dashboard skeleton (bottom bar on phones) and an admin panel skeleton (right sidebar) listing the
§10 pages. The PWA installs as «سِجلّ». Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript 5 + React 18 (web)

**Primary Dependencies**:
- api: FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pydantic-settings, psycopg 3, PyJWT,
  argon2-cffi, uvicorn.
- web: Vite, React Router, TanStack Query, MUI + @emotion/cache + stylis-plugin-rtl,
  vite-plugin-pwa, @fontsource/cairo.
- Exact versions are pinned at implementation to the latest stable releases.

**Storage**: PostgreSQL 16 (`users`, `sessions`, `audit_log`)

**Testing**: pytest + httpx against a real PostgreSQL test DB; Vitest + Testing Library; Playwright
e2e (desktop Chrome, Pixel 7, iPhone 14 profiles)

**Target Platform**: Linux server via Docker Compose behind Caddy (HTTPS); clients are Android
Chrome, iPhone Safari (installed PWA), and desktop browsers

**Project Type**: Web application (API + PWA frontend), monorepo

**Performance Goals**: Sign-in to dashboard under 30 s on a phone (SC-002). Initial app shell
under 300 KB gzipped (excluding fonts) so it loads on weak networks.

**Constraints**: Same-origin deployment (cookie scope); no secrets in git; no request bodies,
passwords, or tokens in logs; Arabic RTL only; UTC storage with Asia/Baghdad display

**Scale/Scope**: Tens of marketers and a few admins; 1 API instance; about 18 placeholder screens

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | Phone normalization lives server-side (`normalize_phone`) and is authoritative; the web mirror only gives early feedback. No request decisions exist yet in 001 |
| II. Identity Documents | ✅ | No card data in 001. Passwords use Argon2id; the log redaction filter is in place; error messages never echo input; the service worker never caches `/api/*` |
| III. Audit Trail | ✅ | `audit_log` with before/after (owner's schema); bootstrap, lockout, and password change are audited; no delete paths for users |
| IV. Immutable Values | ✅ (N/A) | No priced or decided records yet |
| V. Mobile-First & Arabic | ✅ | RTL MUI theme, Cairo font, bottom bar on phones, clear Arabic network errors, PWA tested on Android and iPhone |
| VI. Simplicity | ✅ | Only spec scope; placeholders for later pages; in-process rate limiter instead of a new service |
| VII. Fixed Stack | ✅ | Exactly the constitution stack; services `web`, `api`, `db`, `proxy`; all config from `.env` (+ `.env.example`). No external adapters needed in 001 |
| VIII. Tests | ✅ | pytest for normalization, lockout, roles, password rules, and sessions; Playwright for the critical sign-in flows; tests gate the merge |
| IX. Server Authorization | ✅ | Every router declares `current_user` + `require_roles`; marketer refused on `/api/admin/*` (tested) |
| X. Time | ✅ | `timestamptz` UTC; Baghdad display; `baghdad_month_bounds()` helper tested |

**Result (pre-research)**: PASS. **Result (post-design)**: PASS. Two additions beyond the owner's
schema (`sessions` table, `users.updated_at`) are needed to satisfy spec FR-007/FR-009/FR-012 and
Principle III. They are not constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-project-skeleton-auth/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md
│   └── ui-routes.md
├── checklists/requirements.md
└── tasks.md              # created by /speckit-tasks
```

### Source Code (repository root)

```text
api/
├── Dockerfile
├── entrypoint.sh               # alembic upgrade head → app.cli bootstrap → uvicorn
├── pyproject.toml
├── alembic.ini
├── migrations/versions/        # 0001_users_sessions_audit.py
├── app/
│   ├── main.py                 # FastAPI app, routers, error handlers, log redaction
│   ├── config.py               # pydantic-settings (reads .env)
│   ├── db.py                   # engine, session dependency
│   ├── cli.py                  # bootstrap, seed-demo (dev only)
│   ├── core/
│   │   ├── phone.py            # normalize_phone
│   │   ├── security.py         # argon2, JWT, refresh-token hashing
│   │   ├── timeutil.py         # UTC now, baghdad_month_bounds
│   │   └── ratelimit.py        # per-IP sliding window
│   ├── models/                 # user.py, session.py, audit.py
│   ├── schemas/                # auth.py, user.py
│   ├── services/               # auth_service.py, audit_service.py
│   └── api/
│       ├── deps.py             # current_user, require_roles, allow_password_change
│       ├── auth.py             # /api/auth/*
│       ├── marketer.py         # /api/marketer/dashboard
│       ├── admin.py            # /api/admin/ping
│       └── health.py
└── tests/
    ├── fixtures/phone_cases.json
    ├── unit/                   # test_phone.py, test_security.py, test_timeutil.py
    └── integration/            # test_login.py, test_lockout.py, test_sessions.py,
                                # test_change_password.py, test_roles.py, test_bootstrap.py

web/
├── Dockerfile                  # build → caddy static (SPA fallback)
├── package.json, vite.config.ts (vite-plugin-pwa), tsconfig.json
├── public/icons/               # 192, 512, maskable, apple-touch-icon
└── src/
    ├── main.tsx, App.tsx, router.tsx
    ├── theme/                  # rtl cache, MUI theme, Cairo font
    ├── lib/                    # api.ts (fetch + refresh retry), phone.ts, time.ts
    ├── auth/                   # AuthProvider, guards (RequireAuth, RequireRole, MustChangePasswordGate)
    ├── layouts/                # MarketerLayout (bottom bar / sidebar), AdminLayout (drawer / sidebar)
    ├── pages/                  # Login, ChangePassword, marketer/*, admin/* placeholders
    └── __tests__/

e2e/
├── playwright.config.ts        # desktop, Pixel 7, iPhone 14
└── tests/                      # admin-first-login, marketer-mobile, lockout, roles, logout

deploy/
└── Caddyfile                   # /api/* → api:8000, else → web:80, security headers

docker-compose.yml              # db, api, web, proxy (+ e2e under profile "test")
docker-compose.override.yml     # dev: mounts, uvicorn --reload, vite HMR
.env.example
README.md                       # Arabic: local run with docker compose up
```

**Structure Decision**: Web application monorepo with `api/` and `web/` as the owner specified.
Playwright lives in a separate `e2e/` folder because it exercises the whole composed stack, not
just `web/`.

## Environment variables (`.env.example`)

| Variable | Purpose | Default / example |
|---|---|---|
| `APP_ENV` | `development` / `production` | `development` |
| `SITE_ADDRESS` | Caddy site address | `localhost` (prod: `sijil.t3cftth.net`) |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | db container | `sijil`, `sijil`, `change-me` |
| `DATABASE_URL` | api → db | `postgresql+psycopg://sijil:change-me@db:5432/sijil` |
| `TEST_DATABASE_URL` | pytest | `…/sijil_test` |
| `JWT_SECRET` | access-token signing (≥ 32 random bytes) | `change-me` |
| `ACCESS_TOKEN_MINUTES` | | `15` |
| `REFRESH_TOKEN_DAYS` | | `30` |
| `COOKIE_SECURE` | false only for plain-HTTP LAN testing | `true` |
| `LOCKOUT_THRESHOLD` / `LOCKOUT_MINUTES` | | `5` / `15` |
| `LOGIN_IP_LIMIT` / `LOGIN_IP_WINDOW_MINUTES` | | `20` / `15` |
| `SUPERADMIN_PHONE`, `SUPERADMIN_NAME`, `SUPERADMIN_PASSWORD` | bootstrap (first start only) | synthetic examples |
| `TRUSTED_PROXY_CIDRS` | X-Forwarded-For trust | compose network |

The API refuses to start in `production` if `JWT_SECRET` or a password is still `change-me`.

## Complexity Tracking

| Item | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `e2e` compose service (profile `test`, not started by default) | Principle VIII requires Playwright e2e against the real stack, reproducibly | Running Playwright on each developer host needs browser installs; the four runtime services stay unchanged |
| `sessions` table | Per-device sign-out, rotation, and immediate revocation (FR-007/009/012) | Stateless refresh JWTs cannot be revoked per device without a deny-list table anyway |
