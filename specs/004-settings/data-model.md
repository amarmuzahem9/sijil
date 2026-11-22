# Data Model: Settings (004)

All timestamps are `timestamptz` UTC (Principle X). Migration `0004` creates every table below.

## areas (المناطق)

| Column | Type | Rules |
|---|---|---|
| `id` | bigint identity PK | |
| `name` | text, not null | Trimmed, inner spaces collapsed, 1–100 chars. Unique index on `lower(name)` |
| `is_active` | boolean, not null, default true | |
| `created_at`, `updated_at` | timestamptz, not null | |

## towers (الأبراج)

| Column | Type | Rules |
|---|---|---|
| `id` | bigint identity PK | |
| `code` | text, not null, **unique** | Uppercase; CHECK `code ~ '^[A-Z0-9]{2,20}$'`. Locked while the tower is used |
| `name` | text, not null | 1–100 chars, not unique |
| `area_id` | bigint FK → areas.id, not null, **ON DELETE RESTRICT** | New towers need an active area |
| `is_active` | boolean, not null, default true | |
| `created_at`, `updated_at` | timestamptz, not null | |

## plans (الفئات)

| Column | Type | Rules |
|---|---|---|
| `id` | bigint identity PK | |
| `name` | text, not null | 1–100 chars. Unique index on `lower(name)` |
| `trial_price` | integer, not null | Whole dinars, CHECK 0–10,000,000 |
| `second_price` | integer, not null | Whole dinars, CHECK 0–10,000,000 |
| `is_active` | boolean, not null, default true | |
| `created_at`, `updated_at` | timestamptz, not null | |

## reward_tiers (شرائح المكافآت)

| Column | Type | Rules |
|---|---|---|
| `id` | bigint identity PK | |
| `min_count` | integer, not null, **unique** | CHECK 0–10,000 |
| `rate` | integer, not null | Dinars per subscriber, CHECK 1–10,000,000 |

List rules (service, research R5): 1–20 rows, the first `min_count` is 0, strictly increasing. The
whole list is replaced in one transaction. The seed is `(0, 5000)`, `(30, 7000)`, `(50, 10000)`.
The range shown for tier *i* is «min_i إلى min_{i+1} − 1», and for the last tier «min فأكثر».
Tier changes apply to every unpaid month (system.md §9 v1.3). Paid months snapshot their tier in
feature 016.

## app_settings (عام)

| Column | Type | Rules |
|---|---|---|
| `key` | text PK | Known keys only (service allow-list) |
| `value` | jsonb, not null | |
| `updated_at` | timestamptz, not null | |
| `updated_by` | bigint FK → users.id, null | null = seed |

Known keys: `otp_validity_minutes`, a whole number from 5 to 1,440, seeded to 60.

## "Used" (research R2)

| Item | Used when | Delete when used | Other effect |
|---|---|---|---|
| area | it has any tower (and, later, requests or subscribers) | 409 `item_in_use` | — |
| tower | referenced by requests or subscribers (features 005, 013, 014) | 409 `item_in_use` | code locked (`code_locked`) |
| plan | referenced by requests (feature 005) | 409 `item_in_use` | — |

Every future FK to these tables MUST be `ON DELETE RESTRICT`, and the feature that adds it MUST
register its usage check in `settings_service`.

## Request snapshot (binding on feature 005, research R4)

A request stores these values at submit time: `plan_name`, `trial_price`, `second_price`,
`tower_code`, and `area_name`. It also stores the FKs `plan_id`, `tower_id`, and `area_id`. Later
settings edits never change a request.

## audit_log: actions added

`entity_type` is one of `area`, `tower`, `plan`, `reward_tiers`, `app_setting`, and `entity_id` is
the row id (or the key).

| action | Arabic label |
|---|---|
| `area.created` / `.updated` / `.deactivated` / `.reactivated` / `.deleted` | إضافة منطقة / تعديل منطقة / إيقاف منطقة / تفعيل منطقة / حذف منطقة |
| `tower.*` (same five) | … برج |
| `plan.*` (same five) | … فئة |
| `reward_tiers.updated` | تعديل شرائح المكافآت |
| `app_setting.updated` | تعديل الإعدادات العامة |

New field labels: `code` الرمز, `area` المنطقة, `trial_price` سعر الشهر التجريبي, `second_price`
سعر الشهر الثاني, `tiers` الشرائح, `otp_validity_minutes` مدة صلاحية الرمز (دقيقة). Money fields
are shown with grouping and «د.ع».
