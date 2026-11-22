# API Contract: Settings (004)

This contract follows the conventions of [002 api.md](../../002-accounts-permissions/contracts/api.md).
Routes under `/api/admin/settings` require `require_permission("settings")`, and the main admin
passes. Everyone else gets 403 `forbidden`.

## New error codes

| HTTP | code | message |
|---|---|---|
| 422 | `invalid_name` | «الاسم يجب أن يكون بين 1 و100 حرف» (the 002 accounts keep their 2–100 message) |
| 409 | `name_taken` | «الاسم مستخدم» |
| 422 | `invalid_code` | «الرمز أحرف إنجليزية كبيرة وأرقام فقط» |
| 409 | `code_taken` | «رمز البرج مستخدم» |
| 409 | `code_locked` | «لا يمكن تغيير رمز برج مستعمل» |
| 422 | `area_inactive` | «المنطقة موقوفة» |
| 422 | `invalid_amount` | «المبلغ يجب أن يكون عدداً صحيحاً من 0 إلى 10,000,000» |
| 422 | `invalid_tiers` | Specific reason, e.g. «الشريحة الأولى يجب أن تبدأ من 0» |
| 422 | `invalid_otp_minutes` | «المدة يجب أن تكون من 5 إلى 1,440 دقيقة» |
| 409 | `item_in_use` | «العنصر مستعمل، يمكن إيقافه فقط» |

`invalid_name` keeps its 002 meaning for accounts. Settings raise it with their own message.

## Areas, towers, plans

The same shape is used for each `{kind}` in `areas`, `towers`, `plans`:

| Method & path | Body | Success | Audit |
|---|---|---|---|
| `GET /api/admin/settings/{kind}` | — | 200 `{items: [...]}`, active first, then by name (towers by code) | — |
| `POST /api/admin/settings/{kind}` | create body | 201 item | `{entity}.created` |
| `PATCH /api/admin/settings/{kind}/{id}` | partial body | 200 item | `{entity}.updated` (none if unchanged) |
| `POST /api/admin/settings/{kind}/{id}/deactivate` | — | 200 item | `{entity}.deactivated` (none if already inactive) |
| `POST /api/admin/settings/{kind}/{id}/reactivate` | — | 200 item | `{entity}.reactivated` |
| `DELETE /api/admin/settings/{kind}/{id}` | — | 204 | `{entity}.deleted`; 409 `item_in_use` if used |

The bodies use `extra="forbid"`:

- **area**: `{name}`
- **tower**: `{code, name, area_id}`. PATCH accepts any subset of those fields. `code` is refused
  with `code_locked` while the tower is used.
- **plan**: `{name, trial_price, second_price}`, integers only.

The items:

```json
// area
{"id": 1, "name": "العلم", "is_active": true, "in_use": true, "tower_count": 1}
// tower
{"id": 3, "code": "ALM01", "name": "العلم 1", "area": {"id": 1, "name": "العلم", "is_active": true},
 "is_active": true, "in_use": false}
// plan
{"id": 2, "name": "PLUS", "trial_price": 20000, "second_price": 35000, "is_active": true, "in_use": false}
```

## Reward tiers

| Method & path | Body | Success | Audit |
|---|---|---|---|
| `GET /api/admin/settings/tiers` | — | 200 `{items: [{min_count, rate}]}` ascending | — |
| `PUT /api/admin/settings/tiers` | `{items: [{min_count, rate}]}` | 200, same shape | `reward_tiers.updated` (none if unchanged) |

## General

| Method & path | Body | Success | Audit |
|---|---|---|---|
| `GET /api/admin/settings/general` | — | 200 `{otp_validity_minutes: 60}` | — |
| `PATCH /api/admin/settings/general` | `{otp_validity_minutes}` | 200 | `app_setting.updated` |

## Catalog: any signed-in user (research R3)

`GET /api/catalog` uses `current_user`, so marketers, admins, and the main admin all have access.

```json
{
  "areas":  [{"id": 1, "name": "العلم"}],
  "towers": [{"id": 3, "code": "ALM01", "name": "العلم 1", "area_id": 1}],
  "plans":  [{"id": 2, "name": "PLUS", "trial_price": 20000, "second_price": 35000}]
}
```

The response holds active areas only, active towers whose area is active, and active plans only.
Areas are sorted by name, towers by code, and plans by name.
