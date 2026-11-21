# API Contract: Accounts & Permissions (002)

This contract follows the conventions of [001 api.md](../../001-project-skeleton-auth/contracts/api.md):
- Base path `/api` and Bearer access token.
- Errors use `{code, message}` and never echo submitted values.
- Times are ISO-8601 UTC.
- Every route requires a valid session without a pending password change (`current_user`).

## New and changed error codes

| HTTP | code | message |
|---|---|---|
| 403 | `forbidden` | «ليست لديك صلاحية» (wording shortened from 001) |
| 403 | `protected_account` | «لا يمكن تعديل حساب الأدمن الرئيسي» |
| 404 | `not_found` | Target missing or not of the route's role |
| 409 | `phone_taken` | «رقم الهاتف مستخدم لحساب آخر» |
| 422 | `invalid_phone` | «رقم غير صالح» |
| 422 | `invalid_name` | «الاسم يجب أن يكون بين 2 و100 حرف» |
| 422 | `weak_password` | «كلمة السر يجب أن تكون 8 أحرف على الأقل» (temporary passwords too) |
| 422 | `validation_error` | e.g. unknown permission key |

## Shared shapes

```json
// AccountOut
{
  "id": 12, "name": "…", "phone": "07801234567", "role": "admin",
  "permissions": ["marketers"], "is_active": true, "must_change_password": true,
  "created_at": "2026-11-22T09:00:00Z"
}
```

`permissions` is always `[]` for marketers and for the main admin. The main admin is identified by
`role`.

---

## Admins: main admin only (`require_roles("super_admin")`)

These routes only target rows with `role = 'admin'`. Any other id returns 404 (R4).

| Method & path | Body | Success | Audit |
|---|---|---|---|
| `GET /api/admin/admins` | — | 200 `{items: AccountOut[]}` sorted by name | — |
| `POST /api/admin/admins` | `{name, phone, temporary_password, permissions: string[]}` | 201 `AccountOut` | `user.created` |
| `PATCH /api/admin/admins/{id}` | any of `{name, phone, permissions}` | 200 `AccountOut` | `user.updated` and/or `user.permissions_changed`; none if nothing changed |
| `POST /api/admin/admins/{id}/deactivate` | — | 200 `AccountOut`; revokes all sessions | `user.deactivated` (none if already inactive) |
| `POST /api/admin/admins/{id}/reactivate` | — | 200 `AccountOut` | `user.reactivated` (none if already active) |
| `POST /api/admin/admins/{id}/reset-password` | `{temporary_password}` | 200 `AccountOut`; `must_change_password = true`; revokes all sessions | `user.password_reset` |

Errors: `forbidden` (caller is not the main admin), `not_found`, `phone_taken`, `invalid_phone`,
`invalid_name`, `weak_password`, `validation_error`.

## Marketers: `require_permission("marketers")` (main admin passes)

These routes only target rows with `role = 'marketer'`. Any other id returns 404, so admin
accounts are unreachable here (FR-012).

| Method & path | Body | Success | Audit |
|---|---|---|---|
| `GET /api/admin/marketers` | — | 200 `{items: AccountOut[]}`, active first, then by name | — |
| `POST /api/admin/marketers` | `{name, phone, temporary_password}` | 201 `AccountOut` | `user.created` |
| `PATCH /api/admin/marketers/{id}` | any of `{name, phone}` | 200 `AccountOut` | `user.updated` (none if unchanged) |
| `POST /api/admin/marketers/{id}/deactivate` | — | 200; revokes all sessions | `user.deactivated` |
| `POST /api/admin/marketers/{id}/reactivate` | — | 200 | `user.reactivated` |
| `POST /api/admin/marketers/{id}/reset-password` | `{temporary_password}` | 200; forces a change and revokes sessions | `user.password_reset` |

A body field `permissions` sent to marketer routes is rejected (`validation_error`).

## Audit log: main admin only

### GET /api/admin/audit

Query parameters (all optional):

| Param | Meaning |
|---|---|
| `from`, `to` | `YYYY-MM-DD` Baghdad dates, inclusive; converted to UTC bounds |
| `actor_id` | user id, or `system` for entries with no actor |
| `before_id` | keyset cursor: return entries with `id < before_id` |
| `limit` | default 50, max 100 |

200:

```json
{
  "items": [
    {
      "id": 431, "created_at": "2026-11-22T09:15:02Z", "action": "user.permissions_changed",
      "actor": {"id": 1, "name": "…", "role": "super_admin"},
      "entity_type": "user", "entity_id": "12",
      "target": {"id": 12, "name": "…", "role": "admin"},
      "before": {"permissions": ["marketers"]},
      "after": {"permissions": ["marketers", "settings"]}
    }
  ],
  "has_more": true,
  "next_before_id": 382
}
```

Entries are ordered by `id` descending (newest first). `actor` is `null` for system entries.
`target` is `null` when `entity_type` is not `user`. This endpoint is read-only: no write route
for audit entries exists.

### GET /api/admin/audit/actors

200 `{items: [{id, name, role}]}`: the distinct users who appear as `actor_id`, sorted by name.
The web adds «النظام» for `system`.

## Own account

### GET /api/auth/me

Unchanged from 001. The web refetches it on every route change (R2).

### PATCH /api/auth/me

Body `{name}`. **Main admin only.** Any other role → 403 `forbidden`. 200 returns `UserOut`.
Audit `user.updated` with actor = target. Any other field, including `phone`, is rejected with
`validation_error`.

### POST /api/auth/change-password

Unchanged from 001 (the current password is required).

## Authorization matrix (tested, SC-002)

| Route group | marketer | admin without perm | admin with perm | super_admin |
|---|---|---|---|---|
| `/api/admin/admins*` | 403 | 403 | 403 (no permission grants it) | ✅ |
| `/api/admin/marketers*` | 403 | 403 | ✅ (`marketers`) | ✅ |
| `/api/admin/audit*` | 403 | 403 | 403 | ✅ |
| `PATCH /api/auth/me` | 403 | 403 | 403 | ✅ |
| `/api/admin/ping` | 403 | ✅ | ✅ | ✅ |
