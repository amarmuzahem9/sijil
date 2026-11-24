"""«رسالة الربط» (docs/system.md v1.17 §8.4, specs/012 research R1–R2).

Composed on the server from an allow-list of the request's stored columns each time it is shown,
never stored. It reads no national ID, family number, card reading, image or OTP, so none can leak
(constitution Principle II). Only an accepted or linked request that is not deleted has one.
"""

from typing import Any

_SHOWN_STATUSES = frozenset({"approved", "linked"})


def _money(amount: int) -> str:
    return f"{amount:,}"


def _coordinate(value: float) -> str:
    """Up to 6 decimals (about 0.1 m), without trailing zeros."""
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _address(address: str | None, landmark: str | None) -> str:
    parts = [p.strip() for p in (address, landmark) if p and p.strip()]
    return "، ".join(parts) or "—"


def compose(request: Any) -> str | None:
    """The §8.4 text, one item per line, or None when the request has no link message."""
    if request.is_deleted or request.status not in _SHOWN_STATUSES:
        return None
    return "\n".join(
        [
            f"طلب ربط جديد | رقم الطلب: #{request.number_label}",
            f"الاسم: {request.full_name}",
            f"الهاتف: {request.phone}",
            f"اليوزر: {request.username}",
            f"البرج: {request.tower_name} ({request.tower_code})",
            f"الفئة: {request.plan_name} | التجريبي {_money(request.trial_price)} د.ع"
            f" | الثاني {_money(request.second_price)} د.ع",
            f"العنوان: {_address(request.address, request.landmark)}",
            "الموقع: https://maps.google.com/?q="
            f"{_coordinate(request.location_lat)},{_coordinate(request.location_lng)}",
            f"المسوّق: {request.marketer.name}",
        ]
    )
