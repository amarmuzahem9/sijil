# Quickstart: validating feature 007

## Prerequisites

- The dev stack from 005/006 (`docker compose up`).
- For a real message: an OTPIQ key in `.env`, never committed.
  - **Local or staging test**: a dev key (`sk_dev_…`). OTPIQ sends every message to the
    development phone set in its dashboard.
  - **Production**: a live key (`sk_live_…`).

```env
OTP_MODE=otpiq
OTPIQ_API_KEY=sk_dev_xxxxxxxx
```

- Without a key: use `OTP_MODE=fake` and `OTP_FAKE_CODE=246810` (development only; refused in staging
  and production).

## Automated checks

```bash
docker compose exec api alembic upgrade head
docker compose exec api pytest tests/unit/test_otp_rules.py tests/integration/test_otp.py \
    tests/integration/test_otpiq_sender.py tests/integration/test_log_safety.py
docker compose exec api pytest          # whole suite stays green
docker compose exec web npm test        # OTP control: countdown, states, digits
npx playwright test e2e/tests/otp.spec.ts    # e2e stack uses OTP_MODE=fake, OTP_FAKE_CODE
```

The owner's required tests (all with the fake sender and the `utc_now` override):

| Test | Expected |
|---|---|
| Expiry | The right code at validity + 1 min gives `410 otp_expired` |
| 3 attempts | Two wrong codes give `otp_wrong` with 2 then 1 left. The third gives `otp_cancelled`, and then the right code fails |
| Hourly limit | 5 sends to one phone (moving the clock 61 s between them, across two drafts) succeed. The 6th gives `429 otp_hourly_limit` with the right minutes. At 60 min after the first send, a send works again |
| Context change | After verifying, changing each of phone, tower, category, trial price and second price on its own gives `needs_reverify`, and the draft columns are emptied. Putting the value back stays `needs_reverify` |
| Failed send not counted | With `fail_with="unavailable"`: no row is written, and right after it a real send succeeds (no 60 s wait). Five failures plus five successes in an hour all succeed |

## Manual acceptance on staging (the spec's criterion)

1. Put the dev key in the staging `.env`, set the test phone in the OTPIQ dashboard, and restart `api`.
2. Sign in as a marketer, open a draft, choose a region, tower and category, and type the test phone.
3. Tap «تحقّق». The counter «إعادة الإرسال بعد 60 ثانية» starts.
4. A WhatsApp message with a 6-digit code arrives on the test phone. On the server, check
   `docker compose logs api | grep "otp send"`: one line with `result=ok`, a masked phone, a
   `provider_id`, and `cost=25`. (The response format was already confirmed locally, research R2.)
5. Type the code. ✓ «تم التحقق» appears.
6. Change the category. «يحتاج تحقق جديد» appears.
7. Leak check: `docker compose logs api | grep <the code>` finds nothing, and the code is not in the
   browser network tab.
