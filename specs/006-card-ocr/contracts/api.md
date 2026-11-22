# Contract: app API changes (feature 006)

Base: the 005 draft API ([005 contracts](../../005-subscriber-form/contracts/api.md)). Every
draft call still needs `Authorization` and `X-Client-Id`. Only the owner of the draft may call
these routes; another marketer's draft returns 404 `draft_not_found` (Principle IX).

## Changed: `POST /api/drafts/{id}/images/{side}` (upload)

Unchanged request and status codes. Side effects added (R5):
- that side's `card_readings` row becomes `pending` for the new file (raw/result cleared);
- if both sides now have an image, a reading job is queued after the response.

The response (`DraftOut`) carries the new fields below, with `card_reading` already showing
`pending`.

## Changed: `DraftOut` (GET, PUT, PATCH, upload responses)

New keys:

```json
{
  "no_surname": false,
  "card_fields": {
    "first_name": {"source": "card", "original": "مشترك", "confidence": 0.99, "from": "front"},
    "surname": {"source": "edited", "original": null, "confidence": null, "from": null}
  },
  "national_id_check": {"mrz": "199012345678", "mismatch": true, "confirmed": false},
  "card_reading": {
    "front": {"state": "done", "reason": null, "finished_at": "2026-11-23T10:00:05Z", "surname_empty": false},
    "back": {"state": "reshoot", "reason": "multiple", "finished_at": "2026-11-23T10:00:06Z"}
  }
}
```

- `card_fields` lists only the fields the reading or the marketer touched.
- `national_id_check` is null when there is no verified MRZ.
- `card_reading.<side>` is null when that side has no image.
- The raw reader output is **not** returned.
- `missing` (005) can now also contain `{"field": "national_id_unconfirmed"}`.

## Changed: `PATCH /api/drafts/{id}` body (`changes`)

| Key | Type | Effect |
|---|---|---|
| `no_surname` | bool | `true` clears `surname` and marks it edited; `false` only clears the flag |
| `national_id_confirmed` | bool | `true` confirms the current (or same-request) `national_id` against the verified MRZ; ignored when there is no mismatch |

Any change to one of the eight card fields marks it `edited` (data-model › Rules on save).
`card_fields`, `card_reading` and `national_id_check` are never accepted from the client (422
`validation_error` because of `extra="forbid"`).

## New: `GET /api/drafts/{id}/card-reading`

Lightweight status for the 2-second poll while a reading runs.

```json
{
  "version": 7,
  "same_client": true,
  "front": {"state": "running", "reason": null},
  "back": {"state": "done", "reason": null}
}
```

200; 404 `draft_not_found`. A `running` side older than 60 s is turned into `failed/timeout`
before answering.

## New: `POST /api/drafts/{id}/card-reading/retry`

Re-queues every side in `failed` (any reason) whose image is present; both sides must have an
image. 202 `{front: {...}, back: {...}}` with the new states; 409 `reading_not_retryable` when
no side is failed or a side has no image; 404 `draft_not_found`.

## Changed: `GET /api/client-config`

Adds:

```json
{"open_source": [{"name": "ID_Iraqi_Project", "licence": "AGPL-3.0", "url": "https://github.com/..."}]}
```

`url` comes from `OCR_SOURCE_URL`; when empty, it is the upstream project URL (R12).

## Error codes (new)

| HTTP | Code | Arabic message |
|---|---|---|
| 409 | `reading_not_retryable` | «لا توجد قراءة فاشلة لإعادتها» |

The reading's own outcomes are states, not HTTP errors. Their Arabic texts are shown by the page
(see the UI strings below).

## Environment variables (`.env.example`)

| Name | Default | Meaning |
|---|---|---|
| `OCR_MODE` | `http` | `http` = the `ocr` service; `fake` = the synthetic reader (tests, e2e) |
| `OCR_URL` | `http://ocr:8080` | The reader, on the internal network only |
| `OCR_SOURCE_URL` | empty | The public copy of `ocr/` (FR-022), shown in «حسابي» |

## UI strings (Arabic, as shown)

| Where | Text |
|---|---|
| Card section, reading | «جارٍ قراءة البطاقة» |
| Card section, only one side | «ارفع الوجه الآخر لتبدأ قراءة البطاقة» |
| Field mark | «من البطاقة» / «عُدِّل يدوياً» |
| `no_card` | «لم نتمكن من قراءة وجه البطاقة» / «لم نتمكن من قراءة ظهر البطاقة» |
| `wrong_side` | «هذه صورة الظهر، ضعها في خانتها» / «هذه صورة الوجه، ضعها في خانتها» |
| `not_unified` | «البطاقة الوطنية الموحدة فقط» |
| `multiple` | «يظهر أكثر من مستمسك في الصورة» |
| Re-shoot button and tips | «أعد التصوير» — «بلا لمعة، البطاقة مسطّحة وتملأ الإطار، والوجه في خانته» |
| `failed` | «تعذّرت القراءة الآلية، أكمل يدوياً» + «أعد المحاولة» |
| National ID mismatch | «تأكد من الرقم الوطني» — «على الوجه: … / في الشريط الآلي: …» with «اعتماد هذا الرقم» on each |
| Surname | checkbox «لا يوجد لقب على البطاقة»; hint when the card's surname is empty: «لا يوجد لقب على البطاقة؟ اختر الخيار أدناه أو اسأل المشترك» |
| «حسابي» | «رخص البرمجيات المفتوحة» |
