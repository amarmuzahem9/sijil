# Data Model: Accounts & Permissions (002)

This feature adds **no new tables**. It manages the `users`, `sessions`, and `audit_log` tables
from [001 data-model](../001-project-skeleton-auth/data-model.md). All rules of that document still
apply: timestamps are in UTC, and `users` and `audit_log` rows are never deleted.

## Migration 0002

| Change | Purpose |
|---|---|
| CHECK `users_permissions_known`: `permissions <@ '["review","link","settings","marketers","reports","commissions"]'::jsonb` | Unknown permission keys can never be stored |
| Index `audit_log_actor_created_idx (actor_id, created_at DESC)` | Audit viewer filter by actor (R6) |

Existing constraints still apply: phone format and uniqueness, role values, name length 2–100, and
`permissions = '[]'` unless `role = 'admin'`.

## users — rules added by this feature

| Field | Who may change it | Rule |
|---|---|---|
| `name` | main admin → admins; `marketers` holders and main admin → marketers; main admin → own name | Trimmed, 2–100 chars |
| `phone` | same as name, **never** by the owner | Normalized by §8.1; unique across all accounts → 409 `phone_taken` |
| `role` | nobody (set at creation) | `admin` from admin routes, `marketer` from marketer routes |
| `permissions` | main admin → admins only | Subset of the 6 keys, stored deduplicated in canonical order; `super_admin` stays `[]` (implicit all) |
| `is_active` | main admin → admins; `marketers` holders and main admin → marketers | `super_admin` can never be deactivated (no route reaches it) |
| `password_hash` + `must_change_password` | reset: main admin → admins; `marketers` holders and main admin → marketers; owner → own password (001 flow) | Temporary password ≥ 8 chars; a reset sets `must_change_password = true` |

### Account state

```text
                create (temp password)
                        │
                        ▼
  ┌──────── active, must_change_password ──── owner changes password ───▶ active
  │                     ▲                                                   │
  │                     └──────────── admin password reset ◀────────────────┤
  │                       (revokes all sessions, reason password_reset)     │
  │                                                                         │
  └─ deactivate ──▶ inactive ◀──────────────── deactivate ───────────────────┘
     (revokes all sessions, reason deactivated)
                      │
                      └─ reactivate ──▶ previous flags kept (user signs in again)
```

Deactivating an inactive account, or reactivating an active one, is a no-op: 200, no audit entry.

## Permission ⇄ page map (system.md §10 v1.1)

Shared fixture `page_access.json`, tested on both server and web:

| Page key | Path | Access |
|---|---|---|
| `home` | `/admin` | any admin |
| `pending` | `/admin/pending` | `review` |
| `awaiting_link` | `/admin/awaiting-link` | `link` |
| `subscribers` | `/admin/subscribers` | any of `review`, `link`, `reports` |
| `marketers` | `/admin/marketers` | `marketers` |
| `settings` | `/admin/settings` | `settings` |
| `admins` | `/admin/admins` | main admin only |
| `reports` | `/admin/reports` | `reports` |
| `import` | `/admin/import` | `reports` |
| `backup` | `/admin/backup` | main admin only |
| `audit` | `/admin/audit` | main admin only |
| `account` | `/admin/account` | any admin |

The main admin passes every check.

## Arabic permission labels (FR-001)

| Key | Label |
|---|---|
| `review` | مراجعة الطلبات (قبول/رفض) |
| `link` | تم الربط والتراجع عنه |
| `settings` | الإعدادات والأسعار والشرائح |
| `marketers` | إدارة المسوّقين وتصفير كلمات السر |
| `reports` | التقارير والتصدير والاستيراد |
| `commissions` | العمولات وزر تم الدفع |

## audit_log — actions added

`entity_type = "user"` and `entity_id = <target user id>` for all of them. The actor is the caller.

| action | Arabic label (viewer) | before | after |
|---|---|---|---|
| `user.created` | إنشاء حساب | — | `{name, phone, role, permissions, is_active, must_change_password}` |
| `user.updated` | تعديل بيانات حساب | changed of `{name, phone}` | changed of `{name, phone}` |
| `user.permissions_changed` | تعديل الصلاحيات | `{permissions}` | `{permissions}` |
| `user.deactivated` | إيقاف حساب | `{is_active: true}` | `{is_active: false}` |
| `user.reactivated` | إعادة تفعيل حساب | `{is_active: false}` | `{is_active: true}` |
| `user.password_reset` | تصفير كلمة السر | `{must_change_password}` | `{must_change_password: true}` |

Labels for actions from 001 in the viewer: `user.bootstrap_created` «إنشاء الأدمن الرئيسي»,
`user.locked` «قفل مؤقت بعد محاولات خاطئة», `user.password_changed` «تغيير كلمة السر».

Arabic field labels for before/after: `name` الاسم, `phone` الهاتف, `role` الدور,
`permissions` الصلاحيات, `is_active` الحالة, `must_change_password` يجب تغيير كلمة السر,
`locked_until` مقفل حتى.

Never present in before/after: passwords, temporary passwords, hashes, or tokens. This is
enforced by `audit_service._clean()` and tested.
