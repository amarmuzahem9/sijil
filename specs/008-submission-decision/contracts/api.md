# Contract: app API changes (feature 008)

Every call needs `Authorization`. Draft calls also need `X-Client-Id`. Only the draft's or the
request's owner (an active marketer) may call; anyone else gets 404 (Principle IX). Errors keep the
shape `{"code", "message", ...extra}`.

No response contains:
- another subscriber's data;
- the card readings (`raw`, `result`);
- an OTP code.

## Changed: every `DraftOut`

New field `checks`, and three new missing-item codes (data-model › Derived):

```json
{"checks": {"phone_used": true, "national_id_exists": false, "family_exists": false,
            "additional_confirmed": false},
 "missing": [{"field": "phone_used", "code": "phone_used"}]}
```

| Missing `field` / `code` | Arabic label |
|---|---|
| `national_id_exists` | المشترك لديه اشتراك سابق |
| `family_exists_unconfirmed` | لهذه العائلة اشتراك سابق — اختر «طلب اشتراك إضافي» |
| `phone_used` | المشترك موجود سابقاً، هل يود العودة للخدمة؟ |

## Changed: `PATCH /api/drafts/{id}`

New change key `additional_confirmed: boolean`.

| Status | `code` | When |
|---|---|---|
| 422 | `no_family_match` | `true` sent while the family number matches no existing subscriber |

## Changed: `POST /api/drafts/{id}/otp/send` (the 007 check point)

| Status | `code` | Arabic message |
|---|---|---|
| 409 | `phone_used` | المشترك موجود سابقاً، هل يود العودة للخدمة؟ |

The check runs before the limits and the provider. Nothing is sent and nothing is counted.

## New: `POST /api/drafts/{id}/submit`

Body: `{"version": 12}`, the draft version the page shows. Save pending autosave changes first.

**201** (first submit) or **200** (a repeat for an already submitted draft) returns `RequestOut`:

```json
{"id": 1, "number": 1001, "number_label": "T3C-1001", "type": "new", "status": "approved",
 "reasons": [], "full_name": "…", "tower_code": "ALM03", "area_name": "العلم", "plan_name": "PLUS",
 "trial_price": 20000, "second_price": 35000, "phone": "07801234567",
 "username": "ALM03-07801234567", "submitted_at": "2026-11-23T10:00:00Z",
 "approved_at": "2026-11-23T10:00:00Z", "result": "approved"}
```

- `result`: `approved`, `pending_family` (any `family_exists` reason) or `pending_review`. The page
  picks the text from it:
  - «تمت الموافقة»
  - «بانتظار موافقة المسؤول»
  - «طلبك بانتظار التدقيق»
- `username` is `null` unless the status is `approved` or `linked`.
- `reasons` lists the codes only: `["family_exists", "numbers_edited"]`. It never says who matched.

| Status | `code` | Extra | Arabic message |
|---|---|---|---|
| 404 | `draft_not_found` | — | (existing) |
| 409 | `draft_conflict` | `version`, `same_client` | (existing 005) |
| 409 | `catalog_changed` | `notices` | تغيّرت الإعدادات، راجع الاشتراك وتحقق من الهاتف من جديد |
| 422 | `draft_incomplete` | `missing` | أكمل النواقص قبل الإرسال |
| 409 | `otp_needs_reverify` | — | يحتاج تحقق جديد |
| 409 | `phone_used` | — | المشترك موجود سابقاً، هل يود العودة للخدمة؟ |
| 409 | `national_id_exists` | — | المشترك لديه اشتراك سابق |
| 403 | `forbidden` | — | (existing; caller not an active marketer) |

## New: `GET /api/requests`

The caller's own requests, newest first. The query `status` is optional and can be repeated (for
example `status=pending_review`).

```json
{"items": [{"id": 1, "number_label": "T3C-1001", "full_name": "…", "status": "approved",
            "type": "new", "submitted_at": "…"}]}
```

## New: `GET /api/requests/{id}`

Returns the caller's own `RequestOut`. Another marketer's request gives 404 `request_not_found`.

## Not in 008

- request images (010);
- admin request lists and decisions (010);
- the link message (011);
- search and the remaining tabs (011);
- «إعادة مشترك للخدمة» (009).
