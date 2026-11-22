# Implementation Plan: Settings

**Branch**: `004-settings` | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-settings/spec.md` and the owner's plan input:
the table names, `/api/catalog`, the tabbed UI, the key tests, and the request snapshot rule.

## Summary

This feature adds the admin settings, guarded by the `settings` permission.

**Data**:
- New tables: `areas`, `towers` (unique code, `area_id`), `plans` (two whole-dinar prices),
  `reward_tiers` (unique `min_count`, `rate`), and `app_settings` (key/jsonb).
- Migration `0004` seeds the default tiers and the 60-minute OTP validity.

**Behaviour**:
- Every change is audited with old and new values.
- Items can be deleted only while unused. A registry of usage checks drives the UI flag and the
  API refusal. `ON DELETE RESTRICT` foreign keys back it up in the database.
- A read-only `/api/catalog` gives any signed-in user the active areas, towers, and plans for the
  new-request form (feature 005).

**Web**: `/admin/settings` becomes a tabbed page (المناطق، الأبراج، الفئات، الشرائح، عام), with
money shown as «20,000 د.ع» and input accepted in Arabic digits.

**Future requests**: Requests (005) will snapshot the plan name, the prices, the tower code, and
the area name. Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web), unchanged

**Primary Dependencies**: Unchanged. There are no new packages.

**Storage**: PostgreSQL 16. Migration `0004` adds 5 tables with CHECKs, unique indexes, RESTRICT
FKs, and seeds.

**Testing**: pytest (real PostgreSQL), Vitest, Playwright (desktop and Pixel 7)

**Target Platform / Project Type**: Unchanged web app (`api/` + `web/`)

**Performance Goals**: The acceptance path takes under 3 minutes on a phone (SC-001). Every list is
small, tens of rows.

**Constraints**:
- Authorization is enforced on the server.
- Integers only for money.
- No price change touches recorded requests (Principle IV).
- UTC storage.

**Scale/Scope**: 1 page with 5 tabs, about 20 API routes, and 5 tables

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud | ✅ (N/A) | No request decisions. The tower code format is prepared for the username in §8.2 |
| II. Identity Documents | ✅ (N/A) | No sensitive data |
| III. Audit Trail | ✅ | Every add, edit, state change, delete, tier change, and OTP change is audited with before and after. Deleting unused settings items is allowed by system.md v1.3 and is not covered by the no-delete rules for requests, subscribers, and accounts |
| IV. Immutable Values | ✅ | The snapshot rule for 005 is recorded (R4). RESTRICT FKs and the usage registry prevent deleting what requests reference. Price changes apply to new requests only |
| V. Mobile & Arabic | ✅ | Scrollable tabs, cards on a phone, Arabic-digit money input, «د.ع» formatting |
| VI. Simplicity | ✅ | One current tier list (owner decision). Plain usage registry with no catalog introspection |
| VII. Fixed Stack | ✅ | No new dependencies |
| VIII. Tests | ✅ | The owner's three tests plus validation, audit, and catalog. Playwright covers the acceptance path |
| IX. Server Authorization | ✅ | `require_permission("settings")` on every admin route. `/api/catalog` uses `current_user` and only exposes form-safe fields |
| X. Time | ✅ | Timestamps in UTC |

**Result**: PASS before research and after design. There are no violations.

## Project Structure

```text
specs/004-settings/  plan.md research.md data-model.md quickstart.md contracts/api.md tasks.md

api/migrations/versions/0004_settings.py
api/app/models/catalog.py                  # Area, Tower, Plan, RewardTier, AppSetting
api/app/schemas/settings.py
api/app/services/settings_service.py       # CRUD, validation, usage registry, tiers, app settings, audit
api/app/api/settings.py                    # /api/admin/settings/*
api/app/api/catalog.py                     # /api/catalog
api/app/errors.py                          # new codes
api/tests/integration/test_settings_*.py, test_catalog.py; unit/test_tiers.py

web/src/lib/money.ts                       # parseMoney, formatMoney
web/src/lib/settings.ts                    # typed API
web/src/components/MoneyField.tsx
web/src/pages/admin/settings/{Settings,AreasTab,TowersTab,PlansTab,TiersTab,GeneralTab}.tsx
web/src/lib/labels.ts                      # audit labels for the new actions and fields
web/src/pages/admin/Audit.tsx              # target label for non-user entities, money formatting
web/src/__tests__/money.test.ts, tiers.test.ts
e2e/tests/settings-acceptance.spec.ts
```

**Structure Decision**: Settings get their own model module, service, and router. The admin page
replaces the «الإعدادات» placeholder with a folder of tab components.

## Complexity Tracking

No violations.
