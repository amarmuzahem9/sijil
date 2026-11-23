# API Contract: Admin Review (010)

Every route is under `/api`. Errors use the 001 shape `{code, message}` with an Arabic message.

Permissions:
- `review` covers the main admin and admins with the `review` permission;
- anyone else gets 403 `forbidden` on the list and home routes, and 404 on a single request or image,
  so a request's existence does not leak.

## GET /admin/home — any admin

```json
{
  "today": {"submitted": 3, "approved": 1, "pending": 1, "linked": 0, "rejected": 1},
  "month": {"submitted": 40, "approved": 31, "pending": 1, "linked": 0, "rejected": 4}
}
```

Days and months are in Baghdad time ([R10](../research.md#r10-admin-home-counts-fr-021)). The
response carries no subscriber data.

## GET /admin/requests/pending?reason=family_exists|return|numbers_edited|numbers_conflict — `review`

```json
{
  "total": 2,
  "items": [{
    "id": 12, "number_label": "T3C-1012", "type": "additional",
    "reasons": ["family_exists", "numbers_edited"],
    "marketer_name": "علي", "full_name": "…", "tower_code": "ALM03", "tower_name": "العلم 3",
    "submitted_at": "2026-11-23T08:00:00Z"
  }]
}
```

- Oldest first.
- `reasons` lists only rows whose state is not `not_applicable`.
- An unknown `reason` value gives 422.

## GET /admin/requests/{id} — `review`

Works for a request in any status. A decided request is shown read-only.

```json
{
  "id": 12, "number_label": "T3C-1012", "type": "additional", "status": "pending_review",
  "names": {"first_name": "…", "…": "…"}, "full_name": "…",
  "national_id": "…", "family_number": "…",
  "birth_date": "…", "issue_date": "…", "expiry_date": "…", "birth_place": "…", "issuing_authority": "…",
  "images": [{"id": "uuid", "side": "front"}, {"id": "uuid", "side": "back"}],
  "location": {"lat": 34.7, "lng": 43.6, "source": "gps", "accuracy_m": 12},
  "address": "…", "landmark": "…",
  "area_name": "…", "tower_code": "…", "tower_name": "…", "plan_name": "…",
  "trial_price": 20000, "second_price": 35000,
  "phone": "07…", "otp_verified_at": "…", "username": "ALM03-07…",
  "marketer_name": "علي", "submitted_at": "…",
  "numbers": {
    "national_id": {"reading": "…|null", "mrz": "…|null", "marketer": "…", "current": "…", "edited": true,
                     "pins": [{"value": "…", "source": "reading", "by": "اسم الأدمن", "at": "…"}]},
    "family_number": {"reading": "…|null", "marketer": "…", "current": "…", "edited": false, "pins": []}
  },
  "names_reading": {"first_name": "…|null", "…": "…"},
  "reasons": [{
    "reason": "family_exists", "state": "open", "added_at_review": false, "basis": null,
    "fields": [],
    "record": {"source": "sijil", "ref": "7", "available": true, "full_name": "…", "username": "…",
               "phone": "…", "tower_code": "…", "tower_name": "…", "registered_at": "…",
               "status": "approved", "image_ids": ["uuid"], "expiry": null}
  }],
  "warnings": ["same_person"],
  "decision": null
}
```

- `warnings` is computed live ([R5](../research.md#r5-re-check-and-warnings)).
- `decision` for a decided request:
  `{"status": "approved", "by": "…", "at": "…", "counts_commission": true, "despite_warnings": []}`, or
  `{"status": "rejected", "by": "…", "at": "…", "reason": "other", "label": "…"}`.
- `card_readings` (raw) is never returned.

## GET /admin/request-images/{image_id} — `review`

Returns a JPEG. Each open is logged ([R9](../research.md#r9-image-access-for-review-fr-005)).
404 `image_not_found` when the image does not exist, the caller has no right to it, or the file is
missing.

## POST /admin/requests/{id}/accept — `review`

```json
{"counts_commission": true, "confirm_warnings": ["same_person"]}
```

| Code | When |
|---|---|
| 200 | the request file, now `approved` |
| 409 `already_decided` | the status is no longer pending. `extra.status` = the current status |
| 409 `warnings_unconfirmed` | the current warnings differ from `confirm_warnings`. `extra.warnings` = the current kinds |
| 422 `commission_answer_required` | a `return` without `counts_commission` |
| 422 `validation_error` | `counts_commission` sent for a non-return type |

## POST /admin/requests/{id}/reject — `review`

```json
{"reason": "other", "note": "…"}
```

| Code | When |
|---|---|
| 200 | the request file, now `rejected` |
| 409 `already_decided` | as above |
| 422 `rejection_note_required` | `other` with an empty note, or one under 3 characters after trimming |
| 422 `validation_error` | an unknown reason, a note with a non-`other` reason, or a note over 300 characters |

## POST /admin/requests/{id}/pin — `review`

```json
{"field": "family_number", "source": "reading"}
{"field": "national_id", "source": "typed", "value": "١٩٩٠٠٠٠٠٠٠٠١"}
```

- `value` is accepted only with `source = "typed"`. With `reading`, `mrz` or `marketer` the server
  takes the stored value.
- `mrz` is only for `national_id`.

| Code | When |
|---|---|
| 200 | the request file after the re-check |
| 409 `already_decided` | the request is not pending |
| 422 `pin_source_empty` | the chosen source has no value (e.g. the card did not read it) |
| 422 `invalid_national_id` | not 12 digits after normalization |
| 422 `invalid_family_number` | the comparison key is empty |

## GET /requests/{id} (marketer, changed)

`RequestOut` gains:
- `rejection_reason`: a code or null;
- `rejection_label`: the Arabic label, or the note for `other`;
- `rejected_at`.

Nothing else changes, and nothing about linked records or warnings is added (FR-011).

## New error messages (Arabic)

| Code | Message |
|---|---|
| `already_decided` | تم البت في هذا الطلب مسبقاً |
| `warnings_unconfirmed` | يوجد تحذير على الطلب، أكّد القبول رغم التحذير |
| `commission_answer_required` | حدّد هل تُحتسب عمولة للمسوّق |
| `rejection_note_required` | اكتب سبب الرفض |
| `pin_source_empty` | لا توجد قيمة لهذا المصدر |
| `invalid_national_id` | الرقم الوطني يجب أن يكون 12 رقماً |
| `invalid_family_number` | الرقم العائلي غير صالح |
