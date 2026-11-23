"""WhatsApp OTP sender adapter (Principle VII; specs/007 contracts/otp-sender.md, research R1, R2).

- `OtpiqSender`: the OTPIQ API. Sijil generates the code; OTPIQ only delivers it with its fixed
  verification template, by WhatsApp only (no SMS fallback, owner decision).
- `FakeOtpSender`: in-memory outbox for tests and e2e.

Neither logs the code, the phone, the key, or any request or response body.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, Protocol

import httpx

from app.config import get_settings
from app.core.otp import to_international

log = logging.getLogger("sijil.otp_sender")

SendFailure = Literal["not_configured", "no_credit", "rejected", "busy", "unavailable"]
PROVIDER_TIMEOUT_S = 10.0


class OtpSendError(Exception):
    """The provider did not accept the message. Nothing was sent, nothing is counted."""

    def __init__(self, reason: SendFailure, wait_minutes: int | None = None) -> None:
        super().__init__(reason)
        self.reason: SendFailure = reason
        self.wait_minutes = wait_minutes


@dataclass(frozen=True)
class SendReceipt:
    provider_id: str | None
    cost: int | None  # IQD, when the provider says


class OtpSender(Protocol):
    def send(self, phone: str, code: str) -> SendReceipt: ...


def _body(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _classify_400(body: dict[str, Any]) -> SendFailure:
    text = f"{body.get('error', '')} {body.get('message', '')}".lower()
    if "insufficient credit" in text or "spending threshold" in text:
        return "no_credit"
    return "rejected"  # trial mode, invalid number, unknown 400


class OtpiqSender:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout_s: float = PROVIDER_TIMEOUT_S,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.transport = transport

    def send(self, phone: str, code: str) -> SendReceipt:
        if not self.api_key:
            raise OtpSendError("not_configured")
        payload = {
            "phoneNumber": to_international(phone),
            "smsType": "verification",
            "verificationCode": code,
            "provider": "whatsapp",
        }
        try:
            with httpx.Client(transport=self.transport, timeout=self.timeout_s) as client:
                response = client.post(
                    f"{self.base_url}/sms",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.HTTPError as exc:
            log.warning("otpiq request failed: %s", type(exc).__name__)
            raise OtpSendError("unavailable") from None

        status = response.status_code
        body = _body(response)
        if status == 200:
            provider_id = body.get("smsId") or body.get("messageId")
            cost = body.get("cost")
            return SendReceipt(
                provider_id=str(provider_id) if provider_id else None,
                cost=cost if isinstance(cost, int) else None,
            )
        if status == 400:
            reason: SendFailure = _classify_400(body)
        elif status == 401:
            reason = "not_configured"
        elif status == 429:
            wait = body.get("waitMinutes")
            log.warning("otpiq answered HTTP 429")
            raise OtpSendError("busy", wait if isinstance(wait, int) else None)
        else:
            reason = "unavailable"
        log.warning("otpiq answered HTTP %s reason=%s", status, reason)
        raise OtpSendError(reason)


class FakeOtpSender:
    """In-memory sender. `outbox` holds (phone, code) for tests; never logged."""

    def __init__(self) -> None:
        self.outbox: list[tuple[str, str]] = []
        self.fail_with: SendFailure | None = None
        self.wait_minutes: int | None = None

    def send(self, phone: str, code: str) -> SendReceipt:
        if self.fail_with is not None:
            raise OtpSendError(self.fail_with, self.wait_minutes)
        self.outbox.append((phone, code))
        return SendReceipt(provider_id=f"fake-{len(self.outbox)}", cost=0)


@lru_cache
def _shared_fake() -> FakeOtpSender:
    return FakeOtpSender()


def get_otp_sender() -> OtpSender:
    settings = get_settings()
    if settings.otp_mode == "fake":
        return _shared_fake()
    return OtpiqSender(settings.otpiq_api_key, settings.otpiq_base_url)


def otp_configured() -> bool:
    """False when the real sender has no key («خدمة التحقق غير مهيّأة»)."""
    settings = get_settings()
    return settings.otp_mode == "fake" or bool(settings.otpiq_api_key)
