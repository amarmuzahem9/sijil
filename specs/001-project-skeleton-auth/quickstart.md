# Quickstart & Validation: 001 Project Skeleton & Sign-In

## Prerequisites

- Docker with Compose v2.
- Real-phone and PWA testing is done on the staging server at `https://sijil.t3cftth.net` (see
  `deploy/staging.md`), not over the LAN.

## Run locally

```bash
cp .env.example .env        # set SUPERADMIN_PHONE, SUPERADMIN_NAME, SUPERADMIN_PASSWORD, JWT_SECRET
docker compose up --build   # uses docker-compose.override.yml (dev, hot reload)
docker compose exec api python -m app.cli seed-demo   # synthetic test marketer (dev only)
```

Open `https://localhost`. The first visit warns about Caddy's local certificate; trust it or accept
the warning. The variables are described in `.env.example`.

## Automated checks (must all pass)

```bash
docker compose exec api pytest
docker compose exec web npm test
scripts/e2e.sh                     # isolated stack, fresh DB, Playwright, then torn down
```

## Staging (real devices)

```bash
# on the company server, with a server-only .env (APP_ENV=staging, SITE_ADDRESS=sijil.t3cftth.net)
scripts/deploy-staging.sh          # base compose file only; waits for /api/health; runs seed-demo
```

Run scenarios 3–11 below at `https://sijil.t3cftth.net`: the main admin from a computer, and the
demo marketer from a real Android phone and a real iPhone.

## Validation scenarios

| # | Scenario | Expected |
|---|---|---|
| 1 | Fresh DB, start stack | Logs show the main admin created (no password printed); `GET /api/health` returns ok |
| 2 | Restart with a changed `SUPERADMIN_PASSWORD` | No new admin; the old password still works |
| 3 | Desktop: sign in as main admin with `+964 7xx…` format | Forced to `/change-password`; after saving, the admin panel shows a right sidebar with the 11 pages and «أدمن رئيسي» at the top |
| 4 | Real phone on staging (or a mobile viewport locally): sign in as the demo marketer | Dashboard with two disabled buttons, «تم الربط هذا الشهر: 0», bottom bar with 4 icons |
| 5 | Marketer opens `/admin` | Redirected to `/`; `GET /api/admin/ping` returns 403 |
| 6 | 5 wrong passwords, then the correct one | Locked message with minutes remaining; the correct password is refused until the lock ends |
| 7 | Unknown phone and wrong password | Same message as a wrong password |
| 8 | Close and reopen the app or browser | Still signed in |
| 9 | «تسجيل الخروج» | Back to `/login`; the back button does not reveal pages |
| 10 | Deactivate the demo marketer in the DB while signed in (`UPDATE users SET is_active=false …`, dev only) | The next action shows «الحساب موقوف، راجع الإدارة» |
| 11 | On staging: Android Chrome / iPhone Safari → Add to Home Screen | Icon and name «سِجلّ»; opens full-screen. On iPhone, sign in once inside the installed app |

Manual testing steps for the owner (in Arabic) are delivered with the feature at completion, per
CLAUDE.md.
