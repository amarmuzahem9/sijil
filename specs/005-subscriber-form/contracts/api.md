# API Contract: Drafts and card images (005)

This contract follows the conventions of [004 api.md](../../004-settings/contracts/api.md). Errors
use the shape `{code, message}` with an Arabic message.

Draft routes use `require_roles("marketer")` and the owner check. Every draft call (PUT, PATCH,
image upload, version poll) sends the header `X-Client-Id: <uuid>`, one per page load of the form
(research R3). It is required on writes; a missing or malformed value gets 422
`validation_error`. A draft that does not exist and
a draft owned by someone else both return 404 `draft_not_found`, so its existence is never
revealed.

## New error codes

| HTTP | code | message |
|---|---|---|
| 404 | `draft_not_found` | «المسودة غير موجودة» |
| 409 | `draft_conflict` | «تغيّرت المسودة من جهاز آخر» (+ `version`, `updated_at`, `same_client`) |
| 422 | `too_long` | «النص أطول من المسموح» (+ `field`) |
| 422 | `invalid_name_text` | «الاسم أحرف عربية فقط» (+ `field`) |
| 422 | `location_outside_iraq` | «الموقع خارج العراق، تأكد من الإحداثيات» (+ `field: location`; system.md §5.2 v1.6) |
| 422 | `invalid_choice` | «الاختيار غير صالح» (an id that does not exist) |
| 413 | `image_too_large` | «حجم الصورة أكبر من 5 ميغابايت» |
| 422 | `invalid_image` | «الملف ليس صورة صالحة» |
| 422 | `image_too_big_dimensions` | «أبعاد الصورة أكبر من المسموح، أعد اختيارها» |
| 404 | `image_not_found` | «الصورة غير موجودة» |

## Draft object

```json
{
  "id": "3f0c…", "status": "draft", "version": 7,
  "created_at": "2026-11-22T09:10:00Z", "updated_at": "2026-11-22T09:14:02Z",
  "first_name": "…", "father_name": "…", "grandfather_name": "…",
  "great_grandfather_name": "…", "surname": "…",
  "mother_first_name": "…", "mother_second_name": "…",
  "mother_third_name": null, "mother_surname": null,
  "full_name": "… … … … …",
  "national_id": "…", "family_number": "…",
  "location": {"lat": 33.31, "lng": 44.36, "source": "map", "accuracy_m": null},
  "address": "…", "landmark": "…",
  "area_id": 1, "tower_id": 3, "plan_id": 2,
  "area_name": "العلم", "tower_code": "ALM01", "plan_name": "PLUS",
  "trial_price": 20000, "second_price": 35000,
  "phone_input": "0780 123 4567", "phone_normalized": "07801234567",
  "images": {
    "front": {"id": "a1…", "size_bytes": 412000, "width": 1600, "height": 1012, "created_at": "…"},
    "back": null
  },
  "missing": [{"field": "image_back", "code": "required"}],
  "notices": [{"field": "plan_id", "code": "price_changed",
               "old": {"trial_price": 20000, "second_price": 35000},
               "new": {"trial_price": 22000, "second_price": 35000}}]
}
```

`notices` codes: `choice_unavailable` (the choice was cleared) and `price_changed`.

## Routes

| Method & path | Who | Body | Success | Notes |
|---|---|---|---|---|
| `GET /api/drafts?q=` | marketer | — | 200 `{items:[{id, full_name, tower_code, phone_normalized, updated_at, missing_count, has_images}]}` | Own drafts only, newest `updated_at` first. `q` matches the full name (substring) or the phone digits |
| `PUT /api/drafts/{id}` | marketer | `{changes}` | 201 draft (created), or 200 the existing draft unchanged (idempotent retry by the same owner) | `id` is a client UUID. Another owner's id gives 404 |
| `GET /api/drafts/{id}` | owner | — | 200 draft with `missing` and `notices` | Read-only: notices are computed and not applied (R4) |
| `GET /api/drafts/{id}/version` | owner | — | 200 `{version, updated_at, same_client}` | Polled every 15 s (R3). 404 after deletion |
| `PATCH /api/drafts/{id}` | owner | `{version, changes}` | 200 draft | 409 `draft_conflict` when `version` is stale. Re-copies the catalog values (R4) |
| `DELETE /api/drafts/{id}` | owner | — | 204 | Removes rows and files, audit `draft.deleted` (R8) |
| `POST /api/drafts/{id}/images/{side}` | owner | multipart `file` (JPEG) | 200 draft | `side` is `front` or `back`. Increases `version`. Replaces any existing image |
| `GET /api/draft-images/{image_id}` | owner, main admin, `review` admin | — | 200 `image/jpeg` | `Cache-Control: private, no-store`. Logged in `image_access_log`. Others get 404 |
| `GET /api/client-config` | any signed-in user | — | 200 `{maps: {api_key, map_id, default_center:{lat,lng}} \| null}` | `null` when `GOOGLE_MAPS_API_KEY` is empty (R10) |

### `changes` (PUT/PATCH), `extra="forbid"`

```json
{
  "first_name": "string|null", "father_name": "string|null", "grandfather_name": "string|null",
  "great_grandfather_name": "string|null", "surname": "string|null",
  "mother_first_name": "string|null", "mother_second_name": "string|null",
  "mother_third_name": "string|null", "mother_surname": "string|null",
  "national_id": "string|null", "family_number": "string|null",
  "location": {"lat": 0.0, "lng": 0.0, "source": "gps|map|coords|search", "accuracy_m": 12} ,
  "address": "string|null", "landmark": "string|null",
  "area_id": 1, "tower_id": 3, "plan_id": 2,
  "phone_input": "string|null"
}
```

- An omitted key is unchanged. `null` clears the field. `location: null` clears the pin.
- Text values are trimmed. An empty value becomes `null`.
- Prices, copies and `full_name` are never accepted from the client.
- Name fields follow the name rule of data-model.md; a digit or a non-Arabic letter → 422
  `invalid_name_text`, nothing saved.
- Changing `area_id` clears `tower_id` unless the same PATCH sets a tower of the new area.

### Conflict response (409)

```json
{"code": "draft_conflict", "message": "تغيّرت المسودة من جهاز آخر",
 "version": 9, "updated_at": "2026-11-22T09:15:40Z", "same_client": false}
```

## Environment variables (added to `.env.example`)

| Variable | Default | Purpose |
|---|---|---|
| `UPLOADS_DIR` | `/data/uploads` | Private image storage (the `uploads` volume) |
| `MAX_IMAGE_BYTES` | `5242880` | Upload size limit |
| `GOOGLE_MAPS_API_KEY` | empty | Maps JavaScript API key. Restrict it to the domain in the Google console |
| `GOOGLE_MAPS_MAP_ID` | empty | Map ID for the advanced (draggable) marker |
| `MAP_DEFAULT_CENTER` | `33.3152,44.3661` | Map center used when there is no pin and no position |

> **Feature 007**: `DraftOut` gains `otp`, and two routes are added (`/otp/send`, `/otp/verify`). See
> [specs/007-phone-otp/contracts/api.md](../../007-phone-otp/contracts/api.md).
