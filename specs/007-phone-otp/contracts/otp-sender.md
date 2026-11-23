# Contract: `OtpSender` adapter (feature 007)

The interface comes from the owner: `send(phone, code)`. It lives in `api/app/services/otp_sender.py`.

```python
class OtpSendError(Exception):
    reason: Literal["not_configured", "no_credit", "rejected", "busy", "unavailable"]
    wait_minutes: int | None  # only for "busy"

@dataclass(frozen=True)
class SendReceipt:
    provider_id: str | None
    cost: int | None           # IQD, if the provider says

class OtpSender(Protocol):
    def send(self, phone: str, code: str) -> SendReceipt: ...  # raises OtpSendError
```

- `phone` is always normalized `07XXXXXXXXX`. Each implementation converts it to its own format.
- `code` is 6 ASCII digits.
- An implementation must never log `code`, the full phone, or the request or response body.

## `OtpiqSender`

- Built from `OTPIQ_API_KEY` and `OTPIQ_BASE_URL` (default `https://api.otpiq.com/api`).
- If the key is empty, every call raises `not_configured` without any network call.
- Request:

  ```http
  POST {base}/sms
  Authorization: Bearer {OTPIQ_API_KEY}
  Content-Type: application/json

  {"phoneNumber": "9647801234567", "smsType": "verification",
   "verificationCode": "123456", "provider": "whatsapp"}
  ```

- Timeout 10 s.
- Error mapping: [research.md R2](../research.md). A successful answer returns
  `SendReceipt(provider_id=smsId or messageId, cost=cost)`.
- Tests use `httpx.MockTransport`. No test calls the real API.

## `FakeOtpSender`

- `outbox: list[tuple[str, str]]` holds `(phone, code)` in memory only. Tests read the code from
  here.
- `fail_with: str | None`: when set, `send` raises `OtpSendError(fail_with)` and adds nothing to
  the outbox.
- Never logs.

## Choosing the sender and the code generator

- `OTP_MODE=otpiq|fake` picks the sender (default `otpiq`).
- `OTP_FAKE_CODE` (6 digits, optional) replaces the random code. It is only allowed with
  `OTP_MODE=fake`.
- Both are refused at startup when `APP_ENV` is `staging` or `production` (R8).
- `get_otp_sender()` builds the sender from the settings, like `get_card_reader()` in 006.
  `otp_service.send` takes an optional `sender` argument, and tests pass a `FakeOtpSender` or
  monkeypatch the factory.
