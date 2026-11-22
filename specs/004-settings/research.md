# Research: Settings (004)

The owner fixed the table names, the catalog endpoint, the tabbed UI, the key tests, and the
request snapshot rule in the `/speckit-plan` input. The decisions below fill in the rest.

## R1. Tables and naming

- **Decision**: These tables are added:
  - `areas` for regions (المناطق)
  - `towers`, with `code` unique and an `area_id` FK
  - `plans` for categories (الفئات), with `name`, `trial_price`, `second_price`, `is_active`
  - `reward_tiers`, with `min_count` unique and `rate`
  - `app_settings`, holding a `key` and a jsonb `value`

  Code uses these English names, and the UI uses the Arabic terms of system.md §2.
- **Rationale**: These are the owner's names. `app_settings` as key/value keeps future scalar
  settings (such as the backup path in §15) out of new migrations.

## R2. "Used" and delete (system.md §10 v1.3)

- **Decision**: Two layers.
  1. **Registry check.** `settings_service.usage_count(kind, id)` adds up the counts from a list of
     reference checks. Today the list holds one check: a region is used when it has towers. Later
     features append their own checks, for example "tower used by requests" in 005 and "tower used
     by SAS subscribers" in 014. The list response gives each item an `in_use` flag. The UI hides
     «حذف» and locks the tower code from this flag.
  2. **Database backstop.** Every FK that points at `areas`, `towers`, or `plans` uses
     `ON DELETE RESTRICT`. The service deletes inside a savepoint and turns a foreign-key violation
     into 409 `item_in_use`. A forgotten registry entry can therefore never let a used item be
     deleted.
- **Testing a used tower before requests exist**: The test creates a temporary table with an FK to
  `towers` inside its own transaction. It inserts a row and checks that delete returns 409 and the
  tower is still there. A second test registers a fake reference check and checks that `in_use` is
  true and that the code is locked.
- **Alternatives**: Reading foreign keys from the Postgres catalog at runtime was rejected as too
  clever (Principle VI). A soft-delete flag was rejected because the owner asked for real deletion
  of unused items.

## R3. Catalog endpoint

- **Decision**: `GET /api/catalog` is open to any signed-in user without a pending password change
  (`current_user`), marketers included. It returns only items the new-request form may offer:
  - active areas
  - active towers whose area is also active
  - active plans with their prices

  It does not include tiers or OTP settings.
- **Rationale**: The form in 005 needs exactly this. Marketers must not see deactivated items
  (system.md §10).

## R4. Snapshots on requests (future, binding)

- **Decision**: From feature 005, a request stores copies, taken at submit time, of:
  - the plan name, `trial_price`, and `second_price`
  - the tower code and the area name

  It also keeps the FKs. Settings edits never touch requests (Principle IV, system.md §5.3). This
  feature adds nothing to requests. The rule is recorded in data-model.md so that 005 implements it.

## R5. Validation and normalization

- **Names** (areas, towers, plans):
  - Whitespace is trimmed and collapsed, and the length must be 1–100. Otherwise the error is
    `invalid_name` with the message «الاسم يجب أن يكون بين 1 و100 حرف».
  - An area name or plan name must be unique, ignoring case: a unique index on `lower(name)`. A
    duplicate returns 409 `name_taken` «الاسم مستخدم».
  - Tower names need not be unique.
- **Tower code**:
  - It is uppercased and must match `^[A-Z0-9]{2,20}$`. Otherwise the error is 422 `invalid_code`
    «الرمز أحرف إنجليزية كبيرة وأرقام فقط».
  - It is unique: a duplicate returns 409 `code_taken` «رمز البرج مستخدم».
  - Changing the code while the tower is used returns 409 `code_locked` «لا يمكن تغيير رمز برج
    مستعمل».
- **Money**:
  - Prices are whole dinars from 0 to 10,000,000. Tier rates are from 1 to 10,000,000. The error
    is 422 `invalid_amount`.
  - The API accepts integers only. The web parses Arabic-Indic digits and separators before
    sending (R7).
- **Tiers**:
  - The whole list is replaced in one transaction.
  - There must be 1–20 rows, the first `min_count` must be 0, and the counts must be strictly
    increasing, whole, and at most 10,000.
  - Otherwise the error is 422 `invalid_tiers`, with a specific Arabic reason in `message`.
- **OTP minutes**: A whole number from 5 to 1,440. Otherwise the error is 422 `invalid_otp_minutes`.
- **New tower**: Its area must be active. Otherwise the error is 422 `area_inactive` «المنطقة
  موقوفة». Editing an existing tower keeps its current area even if that area is inactive.

## R6. Audit

- **Decision**: One entry per change, with `entity_type` one of `area`, `tower`, `plan`,
  `reward_tiers`, `app_setting`:

  | action | before / after |
  |---|---|
  | `<entity>.created` | — / all fields |
  | `<entity>.updated` | changed fields only (a price change shows both prices) |
  | `<entity>.deactivated` / `<entity>.reactivated` | `{is_active}` |
  | `<entity>.deleted` | all fields / — |
  | `reward_tiers.updated` | `{tiers: [...]}` / `{tiers: [...]}` |
  | `app_setting.updated` | `{otp_validity_minutes}` |

  No-ops write nothing.
- **Viewer** (002): it gets Arabic labels for these actions and fields. Entries for non-user
  entities show the item's name or code from `after`, or from `before` for a delete, in place of a
  target user.

## R7. Web

- **Decision**:
  - `/admin/settings` (page key `settings`, already guarded) has MUI `Tabs`: المناطق، الأبراج،
    الفئات، الشرائح، عام. The tabs scroll on a phone.
  - Each list reuses the 002 patterns: cards on a phone, a table from `md` up, dialogs, the state
    chip, and `ConfirmDialog` for delete.
  - A `MoneyField` input accepts `٢٠٬٠٠٠`, `20,000`, and `20000`, and shows grouping as you type.
    `formatMoney(n)` gives «20,000 د.ع» using Latin digits with `en-US` grouping, as the owner's
    examples show.
  - Tiers are an editable row list with «إضافة شريحة» and «حذف», plus a computed range column
    («0 إلى 29»، «50 فأكثر») and a single «حفظ».
  - The active tab is kept in the URL (`?tab=towers`) so a reload stays on it.
