# Quickstart & Validation: 002 Accounts & Permissions

## Prerequisites

- The feature 001 stack runs (see [001 quickstart](../001-project-skeleton-auth/quickstart.md)).
- The main admin has signed in once and changed the bootstrap password.
- Use synthetic names and phones only (e.g. «أدمن تجريبي» `07700000101`, «مسوّق تجريبي»
  `07700000201`), never real people.

## Run

```bash
docker compose up --build          # migration 0002 runs at api start (entrypoint)
```

## Automated checks (must all pass)

```bash
scripts/test-all.sh                # ruff, pytest, eslint, typecheck, vitest, Playwright e2e
```

New coverage expected:

- **pytest**:
  - The authorization matrix in [contracts/api.md](./contracts/api.md#authorization-matrix-tested-sc-002).
  - Main-admin protection.
  - Phone uniqueness and normalization on create and edit.
  - Deactivation and reset revoking sessions.
  - No-op actions writing no audit entry.
  - One audit entry per change, with no secrets.
  - Audit filters: Baghdad day bounds, actor, and keyset paging.
  - The `page_access.json` map.
- **vitest**: the access map against the same fixture, and menu filtering per permission set.
- **Playwright**: scenarios A and D below. They run on desktop Chrome and the Pixel 7 profile.

## Validation scenarios

| # | Scenario | Expected |
|---|---|---|
| A | **Acceptance**: the main admin adds «أدمن تجريبي» with only «إدارة المسوّقين» on. In another browser, that admin signs in and changes the password | The admin's menu shows only الرئيسية and المسوّقون (plus حسابي). There is no «الإعدادات» or «الأدمنية والصلاحيات» |
| A2 | Same admin opens `/admin/settings` by address | Redirected to `/admin` with «ليست لديك صلاحية». The settings API calls return 403 |
| A3 | Same admin adds «مسوّق تجريبي». The marketer signs in on a phone viewport | The marketer is forced to change the password, then sees the dashboard |
| B | The main admin turns «الإعدادات» on for that admin. The admin navigates to any page | «الإعدادات» appears without signing out. Turning it off makes it disappear again |
| C | Add an account with a phone already used, typed as `+964 770 000 0201` | «رقم الهاتف مستخدم لحساب آخر» |
| D | The admin deactivates the marketer while the marketer is signed in. The marketer taps anything | Sent to the sign-in screen with «الحساب موقوف، راجع الإدارة». Signing in is refused |
| E | Reactivate the marketer | Signs in again with the same password |
| F | Reset the marketer's password | The open session ends. The next sign-in with the temporary password forces a change |
| G | The main admin's row on الأدمنية | No deactivate or reset action and no switches («كل الصلاحيات»). A direct `POST /api/admin/admins/<main id>/deactivate` returns 404 |
| H | The `marketers`-only admin calls `GET /api/admin/admins` or `/api/admin/audit` | 403 |
| I | «حسابي» as the marketer, the admin, and the main admin | Name and phone are read-only for all three. Only the main admin has «تعديل الاسم», and the new name shows in the top bar |
| J | The main admin opens «سجل العمليات», filters by today and by «أدمن تجريبي» | Entries from A–F appear newest first, with Arabic labels and before/after. There are no password values anywhere |

The Arabic manual test steps for the owner are delivered at completion, per CLAUDE.md.
