# API Contract: Subscriber Deletion (011)

All routes need a signed-in session. Error bodies follow the existing `AppError` shape
(`{code, message}` with an Arabic `message`).

## POST `/admin/requests/{request_id}/delete`

Deletes a request (erases its personal data). Needs `review` and `delete`; the main admin holds both.

**Body**

```json
{ "reason": "duplicate", "confirm_number": "T3C-1005" }
```

- `reason`: `duplicate` | `test` | `entry_error` | `other`.
- `confirm_number`: free text, parsed as in research R6. It must equal the request's number.

**200**: the request file (`RequestFileOut`) in its deleted form (see below).

**Errors** (in check order):

| HTTP | code | When |
|---|---|---|
| 404 | `request_not_found` | the request is missing, or the caller has no `review` |
| 403 | `forbidden` | the caller has `review` but no `delete` |
| 409 | `request_deleted` | already deleted: «تم حذف هذا الطلب مسبقاً» |
| 409 | `request_not_deletable` | status approved or linked: «لا يمكن حذف طلب مقبول أو مربوط» |
| 422 | `validation_error` | unknown reason |
| 422 | `number_mismatch` | the typed number does not match: «رقم الطلب غير مطابق» |

## GET `/admin/requests/by-number/{text}`

Needs `review`. `text` is parsed as in R6.

**200**: `{ "id": 42 }`. The request can be in any status, deleted or not.

**404** `request_not_found`: «لا يوجد طلب بهذا الرقم». Also returned for a caller without `review`.

## Changed: GET `/admin/requests/{request_id}` (`RequestFileOut`)

- New field `deleted`: `null`, or `{ "at": "…", "by_name": "…", "reason": "test" }`.
- New field `can_delete`: true when the caller holds `delete`, the request is pending or rejected, and
  it is not deleted.
- When `deleted` is set:
  - every personal field is `null`;
  - `images`, `pins` and `linked` are `[]`;
  - `warnings` is `[]`;
  - `decision.rejection_note` is `null`.

## Changed: accept, reject, pin

- `POST /admin/requests/{id}/accept`, `…/reject` and `…/pin` return 409 `request_deleted` for a deleted
  request, before the status check.

## Changed: GET `/admin/requests/pending`

- Deleted requests are left out.

## Changed: linked records inside `RequestFileOut.linked`

- A record that is a deleted request comes back as
  `{ "source": "sijil", "ref": "…", "available": false, "deleted": true, "number_label": "T3C-1005" }`
  with no other data.

## Changed: GET `/admin/home`

- `pending` leaves out deleted requests. The other counts are unchanged.

## Changed: GET `/admin/audit`

- Each entry gains `entity_deleted: bool`. It is true when `entity_type = "request"` and that request
  is deleted.
- New action `request.deleted`:
  - `before`: `{status, image_count, pin_count}`;
  - `after`: `{deleted: true, reason}`.

## Changed: marketer GET `/requests` and `/requests/{id}`

- New `result` value: `deleted`.
- New fields:
  - `deleted_at`: timestamp or `null`;
  - `deletion_label`: Arabic reason or `null`.
- For a deleted request, the response carries only:
  - `id`, `number`, `number_label`;
  - `type`, `status`, `result`;
  - `tower_code`, `tower_name`;
  - `submitted_at`, `deleted_at`, `deletion_label`.

  All other fields are `null`. The rejection label for a deleted rejected request is the reason's name
  only.

## Changed: admin accounts (permissions)

- `delete` is a valid permission key in create and update calls for admins. Its label is «حذف مشترك».
