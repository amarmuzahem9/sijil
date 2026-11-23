"""OTPIQ adapter against a mocked transport (specs/007 research.md R2, contracts/otp-sender.md).

No test calls the real API. The success body is the one recorded from the real dev-key call.
"""

import json
import logging

import httpx
import pytest

from app.services.otp_sender import (
    FakeOtpSender,
    OtpiqSender,
    OtpSendError,
    SendReceipt,
    get_otp_sender,
)

KEY = "sk_dev_unit-test-key"
PHONE = "07801234567"
CODE = "482915"
REAL_OK = {
    "message": "SMS task created successfully",
    "smsId": "sms-6f025977e33f56577f947133",
    "remainingCredit": 9975,
    "remainingProjectCredit": 9975,
    "cost": 25,
    "canCover": True,
    "paymentType": "prepaid",
}


def _sender(handler, key: str = KEY) -> OtpiqSender:
    return OtpiqSender(key, "https://api.otpiq.test/api", transport=httpx.MockTransport(handler))


def test_request_shape_and_success() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=REAL_OK)

    receipt = _sender(handler).send(PHONE, CODE)

    assert receipt == SendReceipt(provider_id="sms-6f025977e33f56577f947133", cost=25)
    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == "https://api.otpiq.test/api/sms"
    assert request.headers["Authorization"] == f"Bearer {KEY}"
    assert json.loads(request.content) == {
        "phoneNumber": "9647801234567",
        "smsType": "verification",
        "verificationCode": CODE,
        "provider": "whatsapp",
    }


def test_success_without_cost() -> None:
    receipt = _sender(lambda r: httpx.Response(200, json={"smsId": "sms-x"})).send(PHONE, CODE)
    assert receipt == SendReceipt(provider_id="sms-x", cost=None)


@pytest.mark.parametrize(
    "status,body,reason,wait",
    [
        (
            400,
            {"error": "Insufficient credit, please add more credit", "canCover": False},
            "no_credit",
            None,
        ),
        (
            400,
            {"error": "Project spending threshold of 10,000 IQD would be exceeded"},
            "no_credit",
            None,
        ),
        (
            400,
            {"message": "Account is in trial mode, you can only send sms to your own phone"},
            "rejected",
            None,
        ),
        (400, {"message": "Phone must be a valid number"}, "rejected", None),
        (400, "not json", "rejected", None),
        (401, {"message": "Unauthorized, please use your project api key"}, "not_configured", None),
        (429, {"message": "Rate limit exceeded", "waitMinutes": 8}, "busy", 8),
        (429, {}, "busy", None),
        (500, {"message": "boom"}, "unavailable", None),
        (503, "", "unavailable", None),
    ],
)
def test_error_mapping(status, body, reason, wait) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=body)

    with pytest.raises(OtpSendError) as err:
        _sender(handler).send(PHONE, CODE)
    assert err.value.reason == reason
    assert err.value.wait_minutes == wait


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("slow"), httpx.ConnectError("down")])
def test_network_errors_are_unavailable(exc) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    with pytest.raises(OtpSendError) as err:
        _sender(handler).send(PHONE, CODE)
    assert err.value.reason == "unavailable"


def test_empty_key_makes_no_request() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=REAL_OK)

    with pytest.raises(OtpSendError) as err:
        _sender(handler, key="").send(PHONE, CODE)
    assert err.value.reason == "not_configured"
    assert calls == []


def test_logs_never_hold_code_phone_or_key(caplog, capsys) -> None:
    caplog.set_level(logging.DEBUG)
    responses = iter(
        [
            httpx.Response(200, json=REAL_OK),
            httpx.Response(400, json={"error": f"bad {PHONE} {CODE}"}),
            httpx.Response(500, text=f"{CODE} {KEY}"),
        ]
    )
    sender = _sender(lambda r: next(responses))
    sender.send(PHONE, CODE)
    for _ in range(2):
        with pytest.raises(OtpSendError):
            sender.send(PHONE, CODE)
    captured = caplog.text + capsys.readouterr().err
    for secret in (CODE, PHONE, "9647801234567", KEY):
        assert secret not in captured


def test_fake_sender_outbox_and_failure() -> None:
    fake = FakeOtpSender()
    assert fake.send(PHONE, CODE) == SendReceipt(provider_id="fake-1", cost=0)
    assert fake.outbox == [(PHONE, CODE)]
    fake.fail_with = "busy"
    fake.wait_minutes = 4
    with pytest.raises(OtpSendError) as err:
        fake.send(PHONE, "111111")
    assert (err.value.reason, err.value.wait_minutes) == ("busy", 4)
    assert fake.outbox == [(PHONE, CODE)]


def test_factory_uses_fake_in_tests() -> None:
    assert isinstance(get_otp_sender(), FakeOtpSender)
