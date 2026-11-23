# Contract: app API changes (feature 009)

The 008 rules still hold:
- `Authorization` is required on every call, and `X-Client-Id` on draft calls.
- Only the owner may call; anyone else gets 404.
- Errors have the shape `{"code", "message", ...extra}`.

**No response contains any information about a matched subscriber**: no name, phone, username,
tower, numbers, dates, images, request number, id or count (FR-012).

## Changed: every `DraftOut`

```json
{"checks": {"phone_used": false, "national_id_exists": true, "id_conflict": false,
            "family_exists": false, "additional_confirmed": false,
            "return_available": true, "return_basis": "identity",
            "return_chosen": false, "return_pending": false}}
```

| Missing `field` / `code` | Arabic label |
|---|---|
| `national_id_exists` | المشترك لديه اشتراك سابق — اختر «طلب العودة للخدمة» |
| `phone_used` | المشترك موجود سابقاً، هل يود العودة للخدمة؟ |
| `family_exists_unconfirmed` | لهذه العائلة اشتراك سابق — اختر «إضافة اشتراك ثاني» |
| `return_pending` (new) | يوجد طلب سابق بالانتظار لهذا المشترك |

`id_conflict: true` is a notice («الرقم الوطني مسجّل سابقاً ببيانات مختلفة، سيُراجع الطلب من
الإدارة»). It is not a missing item.

## Changed: `PATCH /api/drafts/{id}`

New change key `return_chosen: boolean`.
- `true` stores the return key. It clears `additional_confirmed` and audits `draft.return_chosen`.
- `false` clears the key and audits `draft.return_withdrawn`.
- `additional_confirmed: true` clears a return choice.

| Status | `code` | When |
|---|---|---|
| 422 | `no_return_match` | `true` sent while there is no return target |

## Changed: `POST /api/drafts/{id}/otp/send`

On a draft with a valid return choice, a phone held only by records of the return target is
allowed. Any other used phone still gives 409 `phone_used`.

## Changed: `POST /api/drafts/{id}/submit`

New outcomes:

| Status | `code` / `result` | Arabic |
|---|---|---|
| 201 | `type: "return"`, `result: "pending_approval"`, `reasons` ⊇ `["return"]` | بانتظار موافقة المسؤول |
| 201 | `reasons` ⊇ `["numbers_conflict"]`, `result: "pending_approval"` (or `pending_family` when a family match is also confirmed) | بانتظار موافقة المسؤول |
| 409 | `return_pending` | يوجد طلب سابق بالانتظار لهذا المشترك |

- 008's `national_id_exists` refusal now happens only when no return is chosen.
- A stale return choice falls back to the no-return rules.
- `username` stays null until approval.

## New: `POST /api/drafts/{id}/contact-admin`

- No body. Returns 204.
- Audits `draft.contact_admin_opened` with the draft id only. The draft does not change.
- Owner only; anyone else gets 404.

## Changed: `GET /api/client-config`

New field `admin_whatsapp`: `"07XXXXXXXXX"` or `null`.

The page builds this link:
`https://wa.me/964XXXXXXXXXX?text=<encoded «مرحباً، أنا المسوّق {name}. عندي مشترك رقم هاتفه مسجّل سابقاً وأحتاج مساعدة الإدارة.»>`

## Changed: `GET/PATCH /api/admin/settings/general` (`settings`)

New field `admin_whatsapp: string | null`.
- The value is normalized by §8.1.
- An invalid value returns 422 `invalid_phone`.
- Empty or null clears the setting.
- Each change is audited `app_setting.updated` with before and after values.

## Request reading (`RequestOut`)

- `type` can be `return`.
- `reasons` can hold `return` and `numbers_conflict`.
- `result` can be `pending_approval`.
- Matched references are never in `RequestOut`.
