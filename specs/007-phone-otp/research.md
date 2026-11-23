# Research: Subscriber Phone Verification by WhatsApp OTP (007)

Decisions for the plan. The owner set the table, the draft columns, the adapter and the test list
(plan › Input). Each decision below fills a gap around those choices.

## R1. Provider: OTPIQ, WhatsApp only, we generate the code

- **Decision**: `POST https://api.otpiq.com/api/sms` with `smsType: "verification"`,
  `verificationCode: <our 6 digits>`, `provider: "whatsapp"`, `phoneNumber: "964" + phone[1:]`.
  Header `Authorization: Bearer <OTPIQ_API_KEY>`. No sender ID, no delivery webhook, no template.
- **Rationale**: OTPIQ has no verify endpoint and its verification type takes a code we supply
  (spec › Provider Findings). `"whatsapp"` stops the fallback to SMS or Telegram (owner: no SMS).
  The fixed template carries only the code.
- **Alternatives**: `"whatsapp-sms"` fallback (rejected by the owner); `custom` message type (lets us
  write text, but needs a sender ID, costs SMS rates, and invites adding data to the message);
  a delivery webhook (needs a public HTTPS callback and adds state the marketer does not need; the
  subscriber reading the code out is the proof of delivery).

## R2. Provider response mapping

| OTPIQ answer | `OtpSendError.reason` | Marketer message |
|---|---|---|
| 200 with `smsId` | — (success) | «أُرسل رمز التحقق عبر الواتساب إلى …» |
| 400 "Insufficient credit…" / "spending threshold…" | `no_credit` | «تعذّر إرسال الرمز، أبلغ الإدارة» |
| 400 "trial mode…" | `rejected` | «تعذّر إرسال الرمز، أبلغ الإدارة» |
| 400 other (invalid number, …) | `rejected` | «تعذّر إرسال الرمز إلى هذا الرقم» |
| 401 | `not_configured` | «خدمة التحقق غير مهيّأة» |
| 429 with `waitMinutes` | `busy` (+ minutes) | «حاول بعد X دقيقة» |
| 5xx, timeout (10 s), network | `unavailable` | «تعذّر إرسال الرمز، حاول مرة أخرى» |

- Matching 400 bodies is by substring on `error`/`message`, case-insensitive. An unknown 400 is
  `rejected`. The log line holds the reason and HTTP status only, never the body (it echoes the
  phone).
- **Confirmed by a real call on 2026-11-23** (dev key, from the local `api` container). The
  OpenAPI shape is the real one; the homepage example (`messageId`, `status`) is not:

  ```json
  {"message":"SMS task created successfully","smsId":"sms-6f025977e33f56577f947133",
   "remainingCredit":9975,"remainingProjectCredit":9975,"cost":25,"canCover":true,
   "paymentType":"prepaid"}
  ```

  - The adapter reads `smsId` and `cost`. `cost` is 25 IQD, matching the owner's price.
  - `GET /sms/track/{smsId}` right after the send answered `status: "pending"`, with
    `channelFlow: [{"channel":"whatsapp","tried":false}]` and the dev phone as `phoneNumber`.
    This confirms that the dev key reroutes the message.
  - `GET /info` answered `{"projectName":"sijil","credit":9975,"projectCredit":9975}`.

## R3. Code generation and hashing

- **Decision**: `secrets.randbelow(10**6)` zero-padded to 6 digits.
  `code_hash = HMAC-SHA256(k, f"{challenge_id}:{code}")`, hex, where
  `k = HMAC-SHA256(JWT_SECRET, "sijil/otp-code/v1")`. Compare with `hmac.compare_digest`.
- **Rationale**: a plain SHA-256 of 6 digits is reversed in microseconds from a database dump. A
  keyed hash needs the server secret. The challenge id makes equal codes hash differently. Deriving
  the key from `JWT_SECRET` avoids a new secret. Rotating it only kills codes that are still pending
  (≤ the validity minutes), because `context_hash` is not keyed (R4).
- **Alternatives**: argon2/bcrypt (slow by design; needless for a 60-minute, 3-attempt code); a
  new `OTP_SECRET` variable (one more secret to manage, no gain).

## R4. Context hash

- **Decision**: `context_hash = SHA-256("v1|{phone_normalized}|{tower_id}|{plan_id}|{trial_price}|{second_price}")`,
  hex. Empty values are written as an empty string. Computed by one function,
  `otp_service.context_hash(draft)`, used at send, verify, every save, and by 008 at submission.
- **Rationale**: ids, not names, identify the tower and category: a rename is not a change of offer.
  Both prices are included (spec › Clarifications). The values are not secret (the draft row holds
  them in plain), so no key is needed, and key rotation cannot drop verifications.
- **Alternatives**: copying the five values into columns (more columns, same effect); comparing
  `tower_code` and `plan_name` (a rename would cancel verifications).

## R5. When verification is cancelled

- **Decision**: in `draft_service.patch`, after `apply_changes`, `apply_subscription` and
  `refresh_copies`, if `otp_verified_at` is set and `context_hash(draft) != otp_context_hash`, clear
  both columns in the same save. The draft output's `otp.status` is also computed against the
  current values, so a stale ✓ never shows.
- **Rationale**: clearing on save (not only comparing on read) meets "putting the old values back
  keeps it cancelled" (spec US2 scenario 5). An admin price change reaches the draft at its next save
  through `refresh_copies` (005 R4). 008 refreshes the copies at submission and compares again.
- **Pending codes**: a code whose `context_hash` no longer matches the draft is treated as cancelled
  (US2 scenario 6). The page closes the code box when `otp.status` leaves `sent`.

## R6. Counting only successful sends, and concurrency

- **Decision**: the row in `otp_challenges` is inserted **after** the provider accepts, in the
  same transaction. A failed send leaves no row, so it counts toward neither the 60 s wait nor the
  5-per-hour limit. The send runs under two transaction-scoped advisory locks, taken in this order:
  `pg_advisory_xact_lock(hashtext('otp:draft:' || draft_id))`, then
  `pg_advisory_xact_lock(hashtext('otp:phone:' || phone))`. The checks run under the locks, then
  the provider call (10 s timeout), then the insert.
- **Rationale**: the limits are counted from the table, so no extra counter is needed. Without the
  locks, two taps or a retried request could both pass the checks and send twice. Advisory locks do
  not lock the draft row, so autosave keeps working during the call.
- **Edge**: if the provider accepted but the commit fails (db down), a message went out with no
  row. This is rare, and it means the subscriber has a code that will not work and the marketer
  resends. It is acceptable.
- **Alternatives**: insert before and delete on failure (a crash mid-call leaves a counted ghost
  row); an in-memory limiter like the login one (lost on restart, not shared across drafts in a
  durable way).

## R7. Limits, computed from `otp_challenges`

- **Resend wait** (per draft): the newest row for `request_id`. If `created_at > now − 60 s`, the
  answer is `429 otp_resend_wait`, and `retry_after_s` comes from the database, not the page.
- **Hourly** (per phone): rows for `phone` with `created_at > now − 60 min`. If there are 5 or
  more, the answer is `429 otp_hourly_limit` with
  `retry_after_min = ceil(oldest_in_window + 60 min − now)`.
- **Attempts**: the challenge row is read with `SELECT … FOR UPDATE`. A wrong code sets
  `attempts += 1`. At 3 the code is dead. A code that is not 6 digits is refused before this and
  is not counted.
- **Expiry**: `expires_at = created_at + otp_validity_minutes` (the 004 setting, read at send).
- All times come from `timeutil.utc_now()`, so tests can move the clock with the existing override.

## R8. Fake sender and how dev/e2e get the code

- **Decision**: `OTP_MODE=otpiq|fake`. The default in `.env.example` is `otpiq`; the e2e and
  test configs use `fake`.
  - `FakeOtpSender` keeps an in-memory `outbox` of `(phone, code)`. Unit and integration tests
    read the code from it.
  - The fake can be set to fail with any `OtpSendError` reason.
  - For Playwright and manual local runs, `OTP_FAKE_CODE=246810` makes the generator return that
    code.
- **Guard**: config refuses `OTP_MODE=fake` and any `OTP_FAKE_CODE` when
  `APP_ENV` is staging or production.
- **Rationale**: with the fixed code, no endpoint or log ever has to reveal a code (FR-016, FR-019),
  and e2e still knows what to type.
- **Alternatives**: a test-only endpoint returning the last code (a code in a server response, even
  in dev, breaks the rule's spirit); logging the code in dev (breaks §13).

## R9. Pre-send phone check (hook for 008)

- **Decision**: `services/phone_checks.py::precheck_for_otp(db, draft, phone) -> AppError | None`.
  It returns `None` in 007. `otp_service.send` calls it after normalization and before the limits.
  008 adds «الهاتف مستخدم» there.

## R10. Secrets and logs

- `OTPIQ_API_KEY` is only in `.env`; `.env.example` has it empty. It is never logged: the redaction
  filter already masks `authorization`. A test asserts the key string never appears in captured logs.
- Each send logs one line: `otp send draft=<id> phone=0780****567 result=<ok|reason> provider_id=<id>
  cost=<n>`. Verify logs `result=<ok|wrong|expired|cancelled>` only. No code, no full phone.
- The `log_safety` integration test is extended to send and verify, then search the captured logs
  and the response bodies for the code and the full phone.

## R11. Pricing note for the owner

The owner confirmed on 2026-11-23 that a WhatsApp message costs **25 IQD**, and the balance is
**10,000 IQD**, which is about **400 sends**:
- A normal verification is one send, 25 IQD per subscriber.
- The worst case per phone is 5 sends an hour (125 IQD).
- Each send's `cost` goes to the log line, so the staging test confirms the price.

The balance is watched in the OTPIQ dashboard. A credit alert inside Sijil is out of scope, and
`no_credit` already gives the marketer «أبلغ الإدارة».
