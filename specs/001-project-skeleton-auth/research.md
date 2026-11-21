# Research: Project Skeleton & Sign-In (001)

All technology choices below follow constitution Principle VII and the owner's planning input.
No open NEEDS CLARIFICATION items remain.

## R1. Repository layout

- **Decision**: Monorepo with `api/` (backend), `web/` (frontend), `deploy/` (Caddy config),
  root `docker-compose.yml` + `docker-compose.override.yml`, root `.env.example`.
- **Rationale**: One branch per feature touches both sides; one compose file runs everything.
- **Alternatives**: Separate repos (rejected: harder to keep API and UI in sync for a small team).

## R2. Session model: short access token + long refresh token

- **Decision**:
  - Access token: JWT (HS256, `JWT_SECRET`), 15-minute lifetime, returned in the JSON body and kept
    **in memory only** by the web app; sent as `Authorization: Bearer`.
  - Refresh token: opaque random 256-bit value in an `httpOnly; Secure; SameSite=Strict` cookie
    scoped to `Path=/api/auth`, 30-day lifetime. Only its SHA-256 hash is stored in a `sessions`
    table.
  - **Rotation with sliding expiry**: every refresh issues a new refresh token and pushes expiry to
    now + 30 days. An active user therefore stays signed in indefinitely (spec FR-008: no idle
    timeout); a device unused for 30 days must sign in again.
  - **Reuse detection**: presenting an already-rotated refresh token revokes that session.
  - On app start the web app calls `POST /api/auth/refresh` to obtain an access token.
- **Rationale**: Satisfies "session stays active until sign-out or deactivation" while keeping
  stolen-token damage small. Keeping the access token out of `localStorage` removes XSS theft of
  long-lived credentials; `SameSite=Strict` + same-origin deployment blocks CSRF on the cookie.
- **Per-device sign-out (FR-009)** = revoke one `sessions` row. **Password reset/change, account
  deactivation (FR-007, FR-012)** = revoke all of the user's sessions.
- **Immediate effect of deactivation and sign-out (FR-007 "next request")**: the access token
  carries `sub` (user id) and `sid` (session id). On every request the auth dependency loads the
  user joined with that session and rejects if `is_active = false` or the session is revoked or
  expired. This costs one indexed lookup per request, which is acceptable at this scale. A pure
  stateless JWT would leave up to 15 minutes of access.
- **Alternatives**: Server-side session cookie only (simpler, but the owner asked for JWT and it
  suits later Capacitor packaging); access token in a cookie too (needs CSRF tokens on every
  mutation).

## R3. iPhone PWA and cookies

- **Decision**: Serve web and API from the same origin (`https://sijil.t3cftth.net`, Caddy routes
  `/api/*`). The refresh cookie is first-party, so it works in Safari's standalone PWA mode.
- **Note**: Safari's 7-day ITP cap applies to script-written storage, not to server-set httpOnly
  cookies on the same origin, so 30-day sessions hold. iOS gives the installed PWA its own cookie jar
  separate from Safari, so the user signs in once inside the installed app (documented in the
  quickstart).
- **Local development**: Caddy serves `https://localhost` with its internal CA. `COOKIE_SECURE`
  defaults to `true` and may be set to `false` only for plain-HTTP testing from a phone on the
  LAN.

## R4. Password hashing

- **Decision**: Argon2id via `argon2-cffi` (`PasswordHasher` defaults), with `check_needs_rehash`
  applied on successful sign-in.
- **Timing-safe unknown phone**: when no user matches, verify against a fixed dummy hash so the
  response time does not reveal whether the account exists (FR-005).

## R5. Lockout and rate limiting

- **Decision**: Per-account counter `failed_logins`. On the 5th consecutive failure set
  `locked_until = now + LOCKOUT_MINUTES` (default 15) and write an audit entry `user.locked`.
  While locked, all attempts are refused (HTTP 423) with the remaining minutes. Success resets the
  counter. The update runs in the same transaction with `SELECT ... FOR UPDATE` to avoid races.
- **Unknown phones / spraying**: an in-process sliding-window limiter per client IP (default
  20 attempts / 15 min) on `POST /api/auth/login`. It is enough for a single API instance and
  needs no new service (Principle VI). Caddy passes the real client IP via `X-Forwarded-For`, and
  the API trusts it only from the proxy network.
- **Alternatives**: Redis-backed limiter (rejected: adds a service not in the constitution's list).

## R6. Phone normalization (§8.1)

- **Decision**: Pure function `normalize_phone(raw: str) -> str | None` in
  `api/app/core/phone.py`:
  1. Translate Arabic-Indic (U+0660–0669) and Extended/Persian (U+06F0–06F9) digits to ASCII.
  2. Drop every non-digit character. This also removes `+`, spaces, dashes, NBSP, U+200E/U+200F,
     U+202A–U+202E, and U+2066–U+2069.
  3. `00964…` → `0…`; `964…` → `0…`.
  4. Exactly 10 digits starting with `7` → prefix `0`.
  5. Valid only if it matches `^07\d{9}$`; otherwise `None`.
- A TypeScript mirror in `web/src/lib/phone.ts` gives instant «رقم غير صالح» feedback. The
  server remains authoritative (Principle I). Both use the same table-driven test cases (a shared
  JSON fixture `api/tests/fixtures/phone_cases.json` is copied into the web tests).
- **Test cases (minimum)**: `07801234567`; `7801234567`; `+9647801234567`; `009647801234567`;
  `9647801234567`; `0780 123 4567`; `0780-123-4567`; `‪07801234567‬` (U+202A…U+202C);
  `‏07801234567` (U+200F); `٠٧٨٠١٢٣٤٥٦٧`; `۰۷۸۰۱۲۳۴۵۶۷`; mixed digits; invalid: empty, `0780123456`
  (too short), `078012345678` (too long), `06801234567`, `+1 555 123 4567`, letters only.

## R7. Bootstrap main admin

- **Decision**: The API container entrypoint runs `alembic upgrade head`, then
  `python -m app.cli bootstrap`, then starts uvicorn. `bootstrap` takes a Postgres advisory lock,
  checks whether any `super_admin` exists, and if none, validates `SUPERADMIN_PHONE` /
  `SUPERADMIN_NAME` / `SUPERADMIN_PASSWORD`. Invalid or missing values exit non-zero with a
  message that never prints the password. Otherwise it creates the user with
  `must_change_password = true` and writes audit `user.bootstrap_created` (actor = null, meaning
  system).
- If a super admin exists, the env values are ignored entirely (spec US1-AS2).

## R8. Dev-only test marketer

- **Decision**: `python -m app.cli seed-demo` creates synthetic accounts («مسوّق تجريبي»,
  `07700000001`) only when `APP_ENV != production`; it refuses to run otherwise. It is idempotent.
- **Rationale**: Account management UI is feature 002; acceptance needs a marketer now. Synthetic
  data only, per the constitution.

## R9. Frontend stack

- **Decision**: React 18 + TypeScript + Vite; React Router (data router); TanStack Query for
  server state; MUI with `@emotion/cache` + `stylis-plugin-rtl` and `dir="rtl"` on `<html>`;
  `vite-plugin-pwa` (manifest `name`/`short_name` «سِجلّ», `lang: ar`, `dir: rtl`,
  `display: standalone`, icons 192/512 + maskable + `apple-touch-icon` 180).
- **Font**: **Cairo**, self-hosted via `@fontsource/cairo` (weights 400/600/700). Bundling the
  font avoids a Google Fonts request on weak networks and keeps the PWA usable offline.
- **Service worker**: precache the app shell only. API responses are never cached (`/api/*` is
  network-only), so no account data is stored by the service worker.
- **Layout**: MUI `useMediaQuery(theme.breakpoints.up('md'))`. Below `md`, the marketer gets a
  `BottomNavigation` (الرئيسية، الطلبات، الإشعارات، حسابي) and the admin gets an app bar with a
  drawer menu. From `md` up, both get a permanent right `Drawer`, plus a top bar with the name and
  role label.
- **Auth state**: a single `AuthProvider` holds the in-memory access token and current user
  (`GET /api/auth/me`). Route guards: `RequireAuth`, `RequireRole`, and `MustChangePasswordGate`.
  An API client wrapper retries once after refresh on `401 token_expired`.
- **Alternatives**: Tailwind or shadcn (more RTL work by hand); Chakra (weaker RTL story).

## R10. Backend structure & libraries

- **Decision**: FastAPI; SQLAlchemy 2 (typed `Mapped[]`, sync engine with `psycopg` 3);
  Alembic; Pydantic v2 + `pydantic-settings`; `PyJWT`; `argon2-cffi`; uvicorn. Sync SQLAlchemy is
  sufficient at this scale and simpler to test.
- **Authorization**: dependencies `current_user` (active, not revoked, not
  `must_change_password` unless the route allows it), `require_roles(...)`, and later
  `require_permission(...)` (feature 002). Every router declares its dependency explicitly
  (Principle IX).
- **Errors**: uniform JSON `{ "code": "...", "message": "<Arabic text>" }`. Messages never echo
  input values or secrets.
- **Logging**: structured JSON logs; a filter redacts `password`, `token`, `authorization`, and
  `cookie` fields; request bodies are never logged.

## R11. Time handling

- **Decision**: All DB timestamps are `timestamptz`, written as `datetime.now(UTC)`. The API emits
  ISO-8601 UTC. The web formats them with `Intl.DateTimeFormat('ar-IQ', { timeZone:
  'Asia/Baghdad' })`. A helper `baghdad_month_bounds()` is added now (unit-tested), ready for the
  feature 011 counter.

## R12. Testing

- **Backend**: pytest + httpx `TestClient` against a real PostgreSQL 16 test database
  (`sijil_test`, created by a fixture; one transaction per test, rolled back). Unit tests cover
  normalize_phone, lockout, password policy, and token logic. Integration tests cover every
  endpoint in [contracts/api.md](./contracts/api.md), including role refusals.
- **Frontend**: Vitest + Testing Library for the phone helper and route guards.
- **E2E**: Playwright in `e2e/` against the composed stack. It covers: super admin desktop sign-in
  with forced change; marketer on mobile viewport (Pixel 7 and iPhone 14 profiles) seeing the
  dashboard and bottom bar; lockout after 5 failures; marketer refused on `/admin`; sign-out.
- **Gate**: `make test` / CI script runs all three; a feature is not merged on failure
  (Principle VIII).

## R13. Containers

- **Decision**:
  - `db`: `postgres:16-alpine`, named volume `pgdata`.
  - `api`: Python 3.12 slim, non-root user, entrypoint per R7.
  - `web`: multi-stage; the build stage runs `vite build`, and the runtime stage is
    `caddy:2-alpine` serving static files with SPA fallback.
  - `proxy`: `caddy:2-alpine`; routes `/api/*` → `api:8000` and everything else → `web:80`; HTTPS
    with automatic certificates for `SITE_ADDRESS` (`sijil.t3cftth.net` in production,
    `localhost` in development). It adds security headers (HSTS, `X-Content-Type-Options`,
    `Referrer-Policy`, and a CSP allowing self only).
  - `docker-compose.override.yml` (development): mounts source, `uvicorn --reload`, the Vite dev
    server with HMR behind the same proxy (WebSocket passthrough), and `APP_ENV=development`.
- Only `proxy` publishes ports (80/443). `db` and `api` stay on the internal network.
