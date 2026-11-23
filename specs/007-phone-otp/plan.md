# Implementation Plan: Subscriber Phone Verification by WhatsApp OTP

**Branch**: `007-phone-otp` | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-phone-otp/spec.md`; the owner's design decisions
(2026-11-23); `docs/system.md` §5.4, §8.1, §8.3, §13, §14; constitution.

Owner decisions:
- the `otp_challenges` table;
- `otp_verified_at` and `otp_context_hash` on the draft, rechecked at submission in 008;
- an `OtpSender.send(phone, code)` adapter, with a fake and an OTPIQ implementation;
- WhatsApp only, no SMS;
- a WhatsApp message costs 25 IQD, and the balance is 10,000 IQD.

## Summary

Next to the subscriber phone, the marketer taps «تحقّق». The server:
- normalizes the stored phone;
- runs the pre-send check (empty until 008);
- applies the 60 s per-draft wait and the 5-per-phone-per-hour limit;
- generates a 6-digit code and sends it through OTPIQ's WhatsApp verification message;
- only after the provider accepts, stores a row in `otp_challenges` with a keyed hash of the code
  and a hash of the context (phone, tower, category, both prices).

The marketer types the code, and the server checks it:
- 3 wrong attempts cancel it;
- it expires after the 004 setting;
- it only counts if the context still matches.

On success the draft gets `otp_verified_at` and `otp_context_hash`. Any save that changes the
context clears them, and the page shows «يحتاج تحقق جديد». The plain code exists only in memory
during the call and in the WhatsApp message.

Details: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12 (api); TypeScript + React 18 (web). Unchanged.

**Primary Dependencies**: none new. `httpx` (already a runtime dependency since 006) calls
OTPIQ; `hmac`, `hashlib` and `secrets` from the standard library.

**Storage**: PostgreSQL 16, migration `0009_otp`:
- new table `otp_challenges`;
- new columns `drafts.otp_verified_at` and `drafts.otp_context_hash`.

See [data-model.md](./data-model.md).

**Testing**:
- **pytest unit tests**: code and context hashing, code-entry normalization, OTPIQ error mapping.
- **pytest integration tests**, using the fake sender and the `utc_now` override, cover the owner's
  list:
  - expiry;
  - 3 attempts;
  - the hourly limit;
  - cancellation by each context field;
  - a failed send is not counted.

  They also cover the resend wait, ownership, the concurrency lock, and log safety.
- **Vitest**: the OTP control states and countdown.
- **Playwright**: send, enter `OTP_FAKE_CODE`, see ✓, change the category, see «يحتاج تحقق جديد».

**Target Platform**: the company Linux server; phones (PWA).

**Project Type**: web app (`api/`, `web/`). No new service.

**Performance Goals**: the send answers within 11 s in the worst case (10 s provider timeout); a
verify answers in under 1 s.

**Constraints**:
- No code in any response, log, audit entry or export.
- The key is in `.env` only.
- WhatsApp only.
- Cost: 25 IQD per send. The 10,000 IQD balance is about 400 sends.

**Scale/Scope**:
- A few sends per marketer per day.
- 2 new routes, 1 table, 2 columns.
- One new web component inside `PhoneSection`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How this plan complies |
|---|---|---|
| I. Anti-Fraud First | ✅ | A change to phone, tower, category or price clears the verification on save (R5), and 008 recomputes the context hash at submission. The pre-send hook is ready for «الهاتف مستخدم» (R9). Verification is a precondition for the decision, not the decision itself. |
| II. Protection of Identity Documents | ✅ | The code is stored only as an HMAC (R3) and never returned or logged. Phones are masked in logs (R10). The provider key is redacted. |
| III. Permanent Audit Trail | ✅ | OTP is not one of the audited events. Challenge rows stay after draft deletion (`SET NULL`) and serve as the send history. |
| IV. Recorded Values Are Immutable | ✅ | `otp_verified_at` is its own fact with its own timestamp. 008 copies it to the request. |
| V. Mobile-First and Arabic | ✅ | The UI is Arabic. The code box opens the numeric keypad, uses `autocomplete="one-time-code"` and accepts pasting and Arabic digits. Pending saves are flushed before sending, for weak networks. |
| VI. Simplicity | ✅ | One table counts everything (R6, R7). No webhook, no queue, no Redis. Nothing outside `docs/system.md` is added. |
| VII. Fixed Technology Stack | ✅ | `OtpSender` adapter with `FakeOtpSender` and `OtpiqSender`. Configuration comes from `.env`. No new service. |
| VIII. Tested Business Rules | ✅ | Each §8.3 rule has a pytest case. The critical flow has a Playwright test. |
| IX. Server-Side Authorization | ✅ | The routes use `get_owned`, so another marketer gets 404. Limits are enforced on the server, whatever the page shows. |
| X. Time Handling | ✅ | Times are stored in UTC and computed from `utc_now()`. Countdowns are durations. |

Gate result: **pass**. Re-checked after Phase 1: **pass** with no change.

## Project Structure

### Documentation (this feature)

```text
specs/007-phone-otp/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md
│   └── otp-sender.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
api/
├── migrations/versions/0009_otp.py              # new: otp_challenges + 2 draft columns
├── app/
│   ├── config.py                                # OTP_MODE, OTPIQ_API_KEY, OTPIQ_BASE_URL, OTP_FAKE_CODE + strict-env guard
│   ├── errors.py                                # new error codes and Arabic messages
│   ├── core/otp.py                              # new: code generation, code/context hashing, code-entry normalization
│   ├── models/otp.py                            # new: OtpChallenge
│   ├── models/draft.py                          # otp_verified_at, otp_context_hash
│   ├── schemas/drafts.py                        # DraftOut.otp, OtpVerifyIn
│   ├── services/otp_sender.py                   # new: OtpSender, OtpiqSender, FakeOtpSender
│   ├── services/otp_service.py                  # new: send, verify, status, context_hash
│   ├── services/phone_checks.py                 # new: precheck_for_otp (008 hook, passes now)
│   ├── services/draft_service.py                # clear verification on context change; otp in to_out
│   ├── api/drafts.py                            # POST /drafts/{id}/otp/send, /otp/verify
│   └── api/client_config.py                     # otp_enabled
└── tests/
    ├── unit/test_otp_rules.py
    ├── integration/test_otp.py
    ├── integration/test_otpiq_sender.py         # httpx.MockTransport
    └── integration/test_log_safety.py           # extended

web/src/
├── lib/otp.ts                                   # new: send/verify calls, error → Arabic text
├── pages/marketer/subscriber/OtpControl.tsx     # new: button, code box, countdown, ✓ / «يحتاج تحقق جديد»
├── pages/marketer/subscriber/PhoneSection.tsx   # hosts OtpControl
└── __tests__/otpControl.test.tsx

e2e/tests/otp.spec.ts
.env.example                                     # OTP_MODE=otpiq, OTPIQ_API_KEY= (empty), OTPIQ_BASE_URL
docker-compose.e2e.yml                           # OTP_MODE=fake, OTP_FAKE_CODE=246810
```

**Structure Decision**: the existing `api/` + `web/` layout. The OTP logic follows the 006 pattern:
an adapter in `services/`, pure rules in `core/`, and a service holding the transaction.

## Complexity Tracking

No violations.
