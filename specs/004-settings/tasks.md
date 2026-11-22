---

description: "Task list for feature 004: Settings"
---

# Tasks: Settings

**Input**: Design documents from `specs/004-settings/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: Required. Constitution Principle VIII, plus the owner's tests: a used tower cannot be
deleted, the code is unique, and permission is checked. Write each test task first and confirm it
fails.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested on
its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 from spec.md
- Paths follow plan.md: `api/` (FastAPI), `web/src/` (React), `e2e/tests/` (Playwright)

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 [P] Create `web/src/lib/money.ts`:
  - `parseMoney(text)` accepts Arabic-Indic and Latin digits, `,` `٬` and spaces, and returns an integer or null
  - `formatMoney(n)` returns «20,000 د.ع»
  - `formatNumber(n)` returns «20,000»
  - Unit tests in `web/src/__tests__/money.test.ts`
- [ ] T002 [P] Add the labels to `web/src/lib/labels.ts`:
  - action labels for `area.*`, `tower.*`, `plan.*`, `reward_tiers.updated`, `app_setting.updated`
  - field labels `code`, `area`, `trial_price`, `second_price`, `tiers`, `otp_validity_minutes`

  All per data-model.md › "audit_log — actions added".

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Write the Alembic migration `api/migrations/versions/0004_settings.py`, creating:
  - `areas`, with data-model.md › `areas.name` (unique on `lower(name)`) and `areas.is_active`
  - `towers`, with data-model.md › `towers.code` (unique, CHECK `^[A-Z0-9]{2,20}$`), `towers.name`, `towers.area_id` (FK **ON DELETE RESTRICT**) and `towers.is_active`
  - `plans`, with data-model.md › `plans.name` (unique on `lower(name)`), `plans.trial_price` and `plans.second_price` (CHECK 0–10,000,000), and `plans.is_active`
  - `reward_tiers`, with data-model.md › `reward_tiers.min_count` (unique, CHECK 0–10,000) and `reward_tiers.rate` (CHECK 1–10,000,000)
  - `app_settings`, with data-model.md › `app_settings.key`, `app_settings.value` and `app_settings.updated_by`

  It seeds the tiers `(0,5000)`, `(30,7000)`, `(50,10000)` and `otp_validity_minutes = 60`, and has a working downgrade.
- [ ] T004 [P] Create the SQLAlchemy models `Area`, `Tower`, `Plan`, `RewardTier` and `AppSetting` in `api/app/models/catalog.py`, mirroring T003. Export them from `api/app/models/__init__.py`.
- [ ] T005 [P] Add the error codes of contracts/api.md › "New error codes" to `api/app/errors.py`. `invalid_name` keeps its 002 message; settings pass their own message.
- [ ] T006 Write the shared part of `api/app/services/settings_service.py`:
  - `clean_name` (1–100 chars), `clean_code` (uppercase, regex, `invalid_code`) and `check_amount` (`invalid_amount`)
  - `_commit`, which maps unique violations to `name_taken` / `code_taken`
  - the usage registry: `register_usage_check(kind, fn)`, `usage_count(db, kind, id)`, `in_use(db, kind, id)`, pre-registered with "area has towers"
  - `delete_item`, which runs the registry check and then a savepoint delete that maps an FK violation to 409 `item_in_use` (research.md R2)
  - generic `set_active` with audit and no-op handling

  Depends on T004 and T005.
- [ ] T007 [P] Add `api/app/schemas/settings.py` with the bodies (`extra="forbid"`, integers for money) and the item shapes of contracts/api.md, each with `in_use`.
- [ ] T008 Create the router skeleton `api/app/api/settings.py` (prefix `/admin/settings`, `require_permission("settings")`) and register it in `api/app/main.py`.
- [ ] T009 [P] Create `web/src/lib/settings.ts` with the typed API calls for areas, towers, plans, tiers, general and the catalog.
- [ ] T010 [P] Create `web/src/components/MoneyField.tsx`: a TextField that uses `parseMoney`, shows grouping, uses LTR input, and shows an inline Arabic error.
- [ ] T011 Create the tabbed page `web/src/pages/admin/settings/Settings.tsx` with MUI scrollable `Tabs` (المناطق، الأبراج، الفئات، الشرائح، عام) and `?tab=` kept in the URL. It replaces the `AdminSettings` placeholder in `web/src/router.tsx` and `web/src/pages/admin/placeholders.tsx`.

**Checkpoint**: The schema, seeds, service base and empty tabs are in place, and all 001–003 tests still pass.

---

## Phase 3: User Story 1 - Regions and towers (Priority: P1) 🎯 MVP

**Goal**: Add, edit, deactivate and reactivate, and delete unused regions and towers.

**Independent Test**: As an admin holding only `settings`, add «العلم» and `alm01`, rename the tower, deactivate and reactivate the region, and see each change in «سجل العمليات».

### Tests for User Story 1

- [ ] T012 [P] [US1] Write integration tests in `api/tests/integration/test_settings_areas_towers.py`:
  - **Permission:** a `settings` admin and the main admin pass; an admin without `settings` and a marketer get 403 on every route.
  - **Areas:** create, duplicate name ignoring spaces → 409, rename, deactivate and reactivate with audit, a no-op writes no audit, an area with towers → no delete and a direct DELETE gives 409 `item_in_use`, an unused area is deleted and audited.
  - **Tower codes:** `alm01` is stored as `ALM01`; a duplicate in any case → 409 `code_taken`; `ALM-01`, `A` and Arabic text → 422 `invalid_code`.
  - **Tower areas:** a new tower in an inactive area → 422 `area_inactive`; moving a tower to another area is allowed.
  - **Used towers:** a temp table with an FK to `towers` plus a row makes DELETE return 409 and the tower stays; a registered fake usage check makes `in_use` true, refuses PATCH `code` with 409 `code_locked`, but still allows `name`.
  - **Unused towers:** DELETE returns 204 with an audit entry.

### Implementation for User Story 1

- [ ] T013 [US1] Add the area and tower functions to `api/app/services/settings_service.py`:
  - list (with `in_use` and `tower_count`), create, update, deactivate, reactivate, delete
  - per data-model.md › `areas.name`, `towers.code`, `towers.area_id` and `towers.is_active`
  - research.md R5 rules: a new tower needs an active area; the code is locked while used
  - audit per data-model.md
- [ ] T014 [US1] Add the area and tower routes of contracts/api.md to `api/app/api/settings.py`.
- [ ] T015 [P] [US1] Build `web/src/pages/admin/settings/AreasTab.tsx`:
  - list with state chip and tower count
  - add/edit dialog, deactivate/reactivate
  - «حذف» shown only when `!in_use`, behind `ConfirmDialog`
- [ ] T016 [P] [US1] Build `web/src/pages/admin/settings/TowersTab.tsx`:
  - list with «ALM01 · العلم 1 · العلم»
  - add/edit dialog: code input in LTR uppercase, area select offering only active areas for new towers, code field disabled when `in_use`
  - state actions and delete as in AreasTab

**Checkpoint**: Regions and towers work end to end.

---

## Phase 4: User Story 2 - Categories, prices and catalog (Priority: P1)

**Goal**: Plans with whole-dinar prices and audited price changes. The read-only catalog (FR-014) is added here because it needs areas, towers and plans.

**Independent Test**: Add PLUS 20,000 / 35,000, change the second price to 40,000, and check the list and the audit entry 35,000 → 40,000. Call `/api/catalog` as a marketer.

### Tests for User Story 2

- [ ] T017 [P] [US2] Write integration tests in `api/tests/integration/test_settings_plans.py`:
  - create PLUS 20000/35000
  - a duplicate name ignoring case → 409
  - prices of -1, 10,000,001, 1.5, `"20,000"` (a string) or missing → 422
  - a price change writes one `plan.updated` entry with `{second_price: 35000}` → `{second_price: 40000}`
  - deactivate and reactivate
  - delete unused → 204
  - permission matrix as in T012
- [ ] T018 [P] [US2] Write integration tests in `api/tests/integration/test_catalog.py`:
  - any signed-in role gets 200, an anonymous call gets 401
  - only active areas, active towers whose area is active, and active plans appear
  - fields are exactly as in contracts/api.md › "Catalog", with no `in_use` or timestamps

### Implementation for User Story 2

- [ ] T019 [US2] Add the plan functions to `api/app/services/settings_service.py` per data-model.md › `plans.name`, `plans.trial_price`, `plans.second_price` and `plans.is_active`, with audit of old and new prices.
- [ ] T020 [US2] Add the plan routes to `api/app/api/settings.py`, and create `api/app/api/catalog.py` (`GET /catalog` with `current_user`) per research.md R3. Register it in `api/app/main.py`.
- [ ] T021 [P] [US2] Build `web/src/pages/admin/settings/PlansTab.tsx`:
  - list with `formatMoney` for both prices
  - dialog using `MoneyField` for both prices
  - state actions and delete as in AreasTab
- [ ] T022 [US2] Move the audit display helpers into `web/src/lib/auditFormat.ts`:
  - `entryTargetLabel(entry)`: the target user's name for `entity_type = user`; otherwise the item label from `after`, or from `before` for deletes (tower → code, area or plan → name, `reward_tiers` → «شرائح المكافآت», `app_setting` → «الإعدادات العامة»)
  - `formatAuditValue(field, value)`: money fields (`trial_price`, `second_price`, tier `rate` inside `tiers`) via `formatMoney`, plus the existing permission, boolean and role formatting

  Add `web/src/__tests__/audit-format.test.ts` covering each entity type, deletes reading `before`, money formatting «35,000 د.ع», and the tier list. Then use both helpers in `web/src/pages/admin/Audit.tsx` (research.md R6).

**Checkpoint**: The acceptance criterion is met (US1 + US2).

---

## Phase 5: User Story 3 - Reward tiers (Priority: P2)

**Goal**: Edit the tier list as a whole, pre-filled with the defaults.

**Independent Test**: See the three defaults with their ranges, add 80 → 12,000, save, and check the audit entry with the list before and after.

- [ ] T023 [P] [US3] Write tests:
  - `api/tests/unit/test_tiers.py`: list rules — the first tier must be 0, counts strictly increasing, no duplicates, 1–20 rows, rate ≥ 1
  - `api/tests/integration/test_settings_tiers.py`:
    - GET returns the seeded defaults
    - PUT replaces the list and writes one `reward_tiers.updated` entry with `{tiers}` before and after
    - an unchanged list writes no audit entry
    - invalid lists → 422 `invalid_tiers` with a specific Arabic message
    - permission is checked
- [ ] T024 [US3] Add `get_tiers` and `replace_tiers` to `api/app/services/settings_service.py`, per data-model.md › `reward_tiers.min_count` and `reward_tiers.rate` and the list rules. Add `GET` and `PUT /admin/settings/tiers` to `api/app/api/settings.py`.
- [ ] T025 [US3] Build `web/src/pages/admin/settings/TiersTab.tsx`:
  - editable rows (count, `MoneyField` rate)
  - a computed range label via a helper `tierRanges()` in `web/src/lib/settings.ts`, tested in `web/src/__tests__/tiers.test.ts`
  - «إضافة شريحة», per-row «حذف», a single «حفظ», and the server error shown inline

---

## Phase 6: User Story 4 - OTP validity (Priority: P3)

**Goal**: Set the OTP validity in minutes (default 60).

**Independent Test**: Change 60 to 30 and see 30 after a reload, with an audit entry 60 → 30. A value of 3 is refused.

- [ ] T026 [P] [US4] Write integration tests in `api/tests/integration/test_settings_general.py`:
  - GET returns 60
  - PATCH 30 → stored, with `app_setting.updated` audit `{otp_validity_minutes: 60}` → `{30}`
  - 4, 1441, 2.5 → 422 `invalid_otp_minutes`
  - an unknown key → 422
  - permission is checked
- [ ] T027 [US4] Add `get_general` and `update_general` (allow-list per data-model.md › `app_settings.key`, `app_settings.value` and `app_settings.updated_by`) to `api/app/services/settings_service.py`, the routes to `api/app/api/settings.py`, and `web/src/pages/admin/settings/GeneralTab.tsx` (a number field in minutes with a range hint).

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T028 [P] Write the Playwright test `e2e/tests/settings-acceptance.spec.ts` (quickstart A, B, D, I):
  - an admin with only «الإعدادات» (seeded through the API) adds «العلم», `alm01` and PLUS `20000` / `٣٥٬٠٠٠`
  - the lists show «ALM01» and «20,000 د.ع» / «35,000 د.ع»
  - a duplicate code is refused
  - «العلم» shows no «حذف»
  - an admin without `settings` is redirected

  Desktop project only.
- [ ] T029 [P] Add 004 to the feature table in `README.md`.
- [ ] T030 Run `scripts/test-all.sh` and fix any failure. Then run `docker compose up -d --build`, restart `web`, and verify the served `/src/pages/admin/settings/Settings.tsx` is the new one. Write the Arabic manual-test steps to `specs/004-settings/manual-test-ar.md`, including the timed check for SC-001 on a phone viewport (the e2e covers desktop only), with the measured time written into the steps.

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: needs Setup and blocks every story. T003 → T004 → T006; T005 → T006; T006/T007 → T008; T009 and T010 → T011.
- **US1 (Phase 3)**: needs Foundational. This is the MVP.
- **US2 (Phase 4)**: needs Foundational. The catalog test (T018) also uses areas and towers, so run it after T013.
- **US3 (Phase 5)** and **US4 (Phase 6)**: need Foundational only. They are independent of US1 and US2.
- **Polish (Phase 7)**: T028 needs US1 and US2. T030 comes last.

**Within each story**: tests first (they must fail), then the service, then the routes, then the UI. The service functions and routes of different stories touch the same files (`settings_service.py`, `settings.py`), so do those tasks one after another, not in parallel.

### Parallel Opportunities

- Setup: T001 and T002.
- Foundational: T004, T005, T007, T009 and T010 after T003.
- US1: T015 and T016 together after T014.
- US3, US4 and the UI tabs of US1 and US2 can proceed in parallel once their service tasks are done.

## Parallel Example: User Story 1

```bash
Task: "T012 Integration tests in api/tests/integration/test_settings_areas_towers.py"
# after T013–T014:
Task: "T015 AreasTab.tsx"
Task: "T016 TowersTab.tsx"
```

---

## Implementation Strategy

### MVP (acceptance criterion)

1. Phase 1, then Phase 2.
2. US1 (regions and towers), then US2 (plans and catalog).
3. **STOP and VALIDATE**: quickstart A–E and H.

### Incremental Delivery

4. US3: tiers.
5. US4: OTP validity.
6. Polish: e2e, README, the full test gate, `docker compose up`, and the Arabic manual steps.

## Notes

- Money is integers end to end. The web parses Arabic-Indic digits before sending.
- Never edit recorded requests. Feature 005 implements the snapshot of data-model.md › "Request snapshot".
- Every future FK to `areas`, `towers` or `plans` must be `ON DELETE RESTRICT` and must register a usage check.
- Use synthetic data in tests. «العلم» and ALM01 are the owner's own examples (§2).
