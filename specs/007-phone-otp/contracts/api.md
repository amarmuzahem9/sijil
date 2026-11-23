# Contract: app API changes (feature 007)

Base: the 005/006 draft API. Every call needs `Authorization` and `X-Client-Id`. Only the draft's
owner may call; any other caller gets 404 `draft_not_found` (Principle IX). No response ever contains
a code (FR-016). Errors use the existing shape `{"code", "message", ...extra}`.

The page saves pending autosave changes **before** calling these routes. The server always works
on the values stored on the draft, never on values sent with the call.

## New: `POST /api/drafts/{id}/otp/send`

Body: none. Sends a new code to the draft's stored phone.

Server steps:
1. Normalize the phone (§8.1).
2. Run the pre-send check (008 hook).
3. Take the locks.
4. Check the 60 s wait and the hourly limit.
5. Call the provider.
6. Insert the challenge.

**200** returns the full `DraftOut`, with `otp.status = "sent"`:

```json
{"otp": {"status": "sent", "phone": "07801234567", "resend_at": "2026-11-23T10:01:00Z",
         "expires_at": "2026-11-23T11:00:00Z", "attempts_left": 3}}
```

| Status | `code` | Extra | Arabic message |
|---|---|---|---|
| 422 | `invalid_phone` | — | رقم غير صالح |
| 409 | `otp_already_verified` | — | الرقم متحقق منه |
| 429 | `otp_resend_wait` | `retry_after_s` | إعادة الإرسال بعد N ثانية |
| 429 | `otp_hourly_limit` | `retry_after_min` | وصلت الحد الأقصى (5 رموز في الساعة) لهذا الرقم، حاول بعد X دقيقة |
| 429 | `otp_provider_busy` | `retry_after_min` | حاول بعد X دقيقة |
| 503 | `otp_not_configured` | — | خدمة التحقق غير مهيّأة |
| 502 | `otp_no_credit` | — | تعذّر إرسال الرمز، أبلغ الإدارة |
| 502 | `otp_rejected` | — | تعذّر إرسال الرمز إلى هذا الرقم |
| 502 | `otp_unavailable` | — | تعذّر إرسال الرمز، حاول مرة أخرى |
| (008) | e.g. `phone_in_use` | (008) | الهاتف مستخدم |

None of the errors creates a row or starts the 60 s wait.

## New: `POST /api/drafts/{id}/otp/verify`

Body: `{"code": "١٢٣٤٥٦"}`. Arabic-Indic digits and spaces are accepted.

**200** returns the full `DraftOut`, with `otp.status = "verified"` and a new `version`.

| Status | `code` | Extra | Arabic message |
|---|---|---|---|
| 422 | `otp_code_format` | — | الرمز 6 أرقام |
| 422 | `otp_wrong` | `attempts_left` (1 or 2) | الرمز غير صحيح، بقيت محاولتان / بقيت محاولة واحدة |
| 410 | `otp_cancelled` | — | أُلغي الرمز بعد 3 محاولات خاطئة، اطلب رمزاً جديداً |
| 410 | `otp_expired` | — | انتهت صلاحية الرمز، اطلب رمزاً جديداً |
| 409 | `otp_no_active` | — | لا يوجد رمز فعّال، اطلب رمزاً جديداً (no code, a newer code replaced it, or phone/tower/category/price changed) |

The third wrong entry returns `410 otp_cancelled`, not `otp_wrong`.

## Changed: `DraftOut` (GET, PUT, PATCH, upload, the two routes above)

The new key `otp` is described in [data-model.md › DraftOut.otp](../data-model.md). A PATCH that
changes the phone, tower, category or prices of a verified draft returns
`otp.status = "needs_reverify"` in the same response.

## Changed: `GET /api/client-config`

The new key `otp_enabled` is `false` when `OTP_MODE=otpiq` and `OTPIQ_API_KEY` is empty. The page
then shows «خدمة التحقق غير مهيّأة» next to the button instead of sending.
