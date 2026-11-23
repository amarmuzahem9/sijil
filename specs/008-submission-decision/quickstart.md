# Quickstart: validating feature 008

## Prerequisites

- Local stack with `OTP_MODE=fake` and `OTP_FAKE_CODE=246810` (e2e and dev only; refused on staging
  and production).
- The demo seed: one area, one tower `ALM03`, one plan `PLUS`, and one marketer.
- Only synthetic sample cards from `test-cards/` or the fake card reader. No real card data.

## Run

```sh
docker compose up -d --build
docker compose exec api alembic upgrade head          # applies 0010_requests
docker compose exec api pytest
cd web && npm test
cd e2e && npx playwright test submit.spec.ts otp.spec.ts
```

## Scenarios

The rules each scenario proves are in [spec.md](./spec.md) and [research.md](./research.md).

| # | Steps | Expected |
|---|---|---|
| 1 | Fill a draft, verify the phone with `246810`, press «إرسال» | «تمت الموافقة», `T3C-1001`, the username `ALM03-07…`; the draft is gone from «مسودات»; «مقبولة» lists it |
| 2 | New draft, same phone written `+964 780…`, press «تحقّق» | «المشترك موجود سابقاً، هل يود العودة للخدمة؟»; no code sent; `otp_challenges` unchanged |
| 3 | New draft, the same national ID typed in Arabic digits | «المشترك لديه اشتراك سابق» under the field; «إرسال» disabled |
| 4 | New draft, different national ID, same family number with spaces or lower case | «لهذه العائلة اشتراك سابق»; press «طلب اشتراك إضافي», verify a new phone, submit → «بانتظار موافقة المسؤول»; reason `family_exists` |
| 5 | Read a card, change one digit of the family number, submit | «طلبك بانتظار التدقيق»; reason `numbers_edited` with `fields: ["family_number"]` |
| 6 | Read a card, edit only a name, submit | approved |
| 7 | Set request 1 to `rejected` in the database (010 has no screen yet), retry scenario 2 | the phone is no longer blocked (Q1) |
| 8 | After verifying, change the category in another tab, press «إرسال» | «يحتاج تحقق جديد» |
| 9 | Press «إرسال» twice fast | one request and one number |
| 10 | After 1, raise the PLUS price in the settings | request 1 keeps the old prices |
| 11 | Look at the API logs and the audit log after 1–5 | no national ID, family number or full phone; `request.submitted` and `request.submit_refused` present |

The owner's Arabic manual-test steps go in `manual-test-ar.md` at the end of implementation.
