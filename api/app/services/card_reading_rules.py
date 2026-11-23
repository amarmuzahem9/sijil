"""Rules for one side of a card reading (specs/006 research R6, R7; owner decisions 4 and 6).

The reader (`ocr` service) reports every document it detected in a photo, with no decision.
These pure functions decide what that photo means for the slot it was uploaded to:

1. Another document type (licence, residence card, …) alone → «البطاقة الوطنية الموحدة فقط».
2. Card candidates: front/back detections that passed the second check (≥ 0.50).
3. Duplicates merge: same verified MRZ document number, or boxes overlapping (IoU ≥ 0.5).
4. A second document counts only if it is high-confidence (≥ 0.90) or has readable fields.
5. Outcome: no candidate → no_card; only the other side → wrong_side; two or more → multiple;
   otherwise the expected side is `done` (its fields may still be partly empty).

No card content is logged here.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.core.arabic_name import InvalidArabicName, clean_place_text
from app.core.card_reading import (
    BACK_CLASS,
    BIRTH_PLACE_MAX,
    DUPLICATE_IOU,
    FRONT_CLASS,
    FRONT_LABELS,
    OTHER_DOC_MIN,
    OTHER_DOCUMENT_CLASSES,
    PRINTED_BIRTH_MIN_AGREEMENT,
    SECOND_DOC_HIGH,
    SECOND_PASS_MIN,
    SIDE_CLASS,
    birth_century,
    fix_place_separators,
    issue_for_expiry,
    looks_like_place,
    mrz_date,
    mrz_national_id,
    mrz_verified,
    normalize_family_number,
    parse_printed_date,
    snap_authority,
)


@dataclass(frozen=True)
class SideOutcome:
    state: str  # "done" | "reshoot"
    reason: str | None  # reshoot: no_card | wrong_side | not_unified | multiple
    result: dict[str, Any] | None  # data-model.md › card_readings.result (for "done")


def _cls(detection: dict[str, Any]) -> str:
    return str(detection.get("class") or "").strip().lower()


def _text(detection: dict[str, Any], label: str) -> str:
    item = (detection.get("fields") or {}).get(label) or {}
    return str(item.get("text") or "").strip()


def _readable_count(detection: dict[str, Any]) -> int:
    """How many readable card fields a detection has (R6.4); used to rank and to count."""
    if _cls(detection) == FRONT_CLASS:
        return sum(1 for label in FRONT_LABELS if _text(detection, label))
    count = 1 if _text(detection, "nu_f") else 0
    zone = detection.get("mrz") or {}
    if zone.get("mrz_type") == "TD1":
        count += 2
    return count


def _has_readable_fields(detection: dict[str, Any]) -> bool:
    if _cls(detection) == FRONT_CLASS:
        return _readable_count(detection) >= 2
    return _readable_count(detection) >= 1


def _iou(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def _verified_number(detection: dict[str, Any]) -> str | None:
    zone = detection.get("mrz")
    return (zone or {}).get("number") if mrz_verified(zone) else None


def _same_card(a: dict[str, Any], b: dict[str, Any]) -> bool:
    number_a, number_b = _verified_number(a), _verified_number(b)
    if number_a and number_a == number_b:
        return True
    box_a, box_b = a.get("box"), b.get("box")
    return bool(box_a and box_b) and _iou(box_a, box_b) >= DUPLICATE_IOU


def _rank(detection: dict[str, Any]) -> tuple[int, float]:
    return _readable_count(detection), float(detection.get("second_pass") or 0.0)


def _merge(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group detections of the same physical card; keep the best of each group (R6.3)."""
    groups: list[list[dict[str, Any]]] = []
    for detection in sorted(candidates, key=_rank, reverse=True):
        for group in groups:
            if any(_same_card(detection, member) for member in group):
                group.append(detection)
                break
        else:
            groups.append([detection])
    return [max(group, key=_rank) for group in groups]


def _front_result(detection: dict[str, Any]) -> dict[str, Any]:
    fields = {
        label: {
            "text": str(item.get("text") or "").strip(),
            "confidence": item.get("confidence"),
        }
        for label, item in (detection.get("fields") or {}).items()
        if label in FRONT_LABELS
    }
    return {"fields": fields, "surname_empty": not fields.get("last", {}).get("text")}


def _back_result(detection: dict[str, Any]) -> dict[str, Any]:
    family = (detection.get("fields") or {}).get("nu_f")
    zone = detection.get("mrz")
    return {
        "family_number": (
            {
                "text": str(family.get("text") or "").strip(),
                "normalized": normalize_family_number(family.get("text")),
                "confidence": family.get("confidence"),
            }
            if family
            else None
        ),
        "mrz": (
            {
                "verified": mrz_verified(zone),
                "national_id": mrz_national_id(zone),
                "document_number": (zone or {}).get("number"),
                "checks": {
                    "number": bool(zone.get("valid_number")),
                    "birth": bool(zone.get("valid_date_of_birth")),
                    "expiry": bool(zone.get("valid_expiration_date")),
                    "composite": zone.get("valid_composite"),
                },
            }
            if zone
            else None
        ),
        # Raw material for the back fields (R13); accepted later with the national ID.
        "back_fields": _back_fields_raw(detection),
    }


def _back_fields_raw(detection: dict[str, Any]) -> dict[str, Any]:
    zone = detection.get("mrz") or {}
    city = (detection.get("fields") or {}).get("city") or {}
    bands = detection.get("bands") or {}
    return {
        "mrz_birth": zone.get("date_of_birth") if zone.get("valid_date_of_birth") else None,
        "mrz_expiry": zone.get("expiration_date") if zone.get("valid_expiration_date") else None,
        "birth_place": {
            "text": str(city.get("text") or "").strip(),
            "confidence": city.get("confidence"),
        },
        "issue": [str(t) for t in bands.get("issue") or []],
        "expiry": [str(t) for t in bands.get("expiry") or []],
        "birth": [str(t) for t in bands.get("birth") or []],
        "authority": bands.get("authority") or None,
    }


def _proposal(value: Any, original: Any, source: str, confidence: float | None = None) -> dict:
    return {
        "value": value,
        "original": original.isoformat() if isinstance(original, date) else original,
        "confidence": confidence,
        "from": source,
    }


def resolve_back_fields(
    raw: dict[str, Any] | None, national_id: str | None, today: date
) -> dict[str, dict]:
    """Accept the back fields only when cross-checked (research R13, FR-026–FR-028).

    Returns `{field: {value, original, confidence, from}}`; `value` is None when the reading was
    not confirmed (the marketer types it), and `original` keeps what was read.
    """
    if not raw:
        return {}
    out: dict[str, dict] = {}
    issue_c = [d for d in (parse_printed_date(t) for t in raw.get("issue") or []) if d]
    expiry_c = [d for d in (parse_printed_date(t) for t in raw.get("expiry") or []) if d]
    birth_c = [d for d in (parse_printed_date(t) for t in raw.get("birth") or []) if d]

    # Expiry: MRZ (own check digit, 20xx), else printed and confirmed by a printed issue date.
    expiry = mrz_date(raw.get("mrz_expiry"), "20")
    expiry_from = "mrz" if expiry else None
    issue = None
    if expiry is None:
        for candidate in expiry_c:
            if issue_for_expiry(candidate) in issue_c:
                expiry, issue, expiry_from = candidate, issue_for_expiry(candidate), "back"
                break
    elif issue_for_expiry(expiry) in issue_c:
        issue = issue_for_expiry(expiry)
    out["expiry_date"] = _proposal(
        expiry, expiry or (raw.get("expiry") or [None])[0], expiry_from or "back"
    )
    out["issue_date"] = _proposal(issue, issue or (raw.get("issue") or [None])[0], "back")

    # Birth: MRZ (own check digit; century from the national ID), else printed with agreement
    # and the national ID's birth year.
    birth, birth_from = None, "back"
    yymmdd = raw.get("mrz_birth")
    if yymmdd and len(yymmdd) == 6 and yymmdd.isdigit():
        birth = mrz_date(yymmdd, birth_century(national_id, yymmdd[:2], today))
        birth_from = "mrz" if birth else "back"
    if birth is None and national_id and len(national_id) == 12:
        counts = Counter(d for d in birth_c if str(d.year) == national_id[:4])
        agreed = [d for d, n in counts.items() if n >= PRINTED_BIRTH_MIN_AGREEMENT]
        birth = agreed[0] if len(agreed) == 1 else None
    out["birth_date"] = _proposal(birth, birth or (raw.get("birth") or [None])[0], birth_from)

    place = raw.get("birth_place") or {}
    text = str(place.get("text") or "").strip()
    try:
        cleaned = clean_place_text(fix_place_separators(text))
    except InvalidArabicName:
        cleaned = None
    if cleaned and (len(cleaned) > BIRTH_PLACE_MAX or not looks_like_place(cleaned)):
        cleaned = None
    if text:
        out["birth_place"] = _proposal(cleaned, cleaned or text, "back", place.get("confidence"))

    authority = raw.get("authority") or {}
    text = str(authority.get("text") or "").strip()
    if text:
        snapped = snap_authority(text)
        out["issuing_authority"] = _proposal(
            snapped, snapped or text, "back", authority.get("confidence")
        )
    return {field: p for field, p in out.items() if p["value"] is not None or p["original"]}


def evaluate_side(raw: dict[str, Any], side: str) -> SideOutcome:
    """Decide what the reader's answer for one photo means for the `side` slot (R6)."""
    detections = list(raw.get("detections") or [])
    expected = SIDE_CLASS[side]

    candidates = [
        d
        for d in detections
        if _cls(d) in (FRONT_CLASS, BACK_CLASS)
        and float(d.get("second_pass") or 0.0) >= SECOND_PASS_MIN
    ]
    if not candidates:
        other = any(
            _cls(d) in OTHER_DOCUMENT_CLASSES and float(d.get("confidence") or 0.0) >= OTHER_DOC_MIN
            for d in detections
        )
        return SideOutcome("reshoot", "not_unified" if other else "no_card", None)

    cards = _merge(candidates)
    expected_cards = [d for d in cards if _cls(d) == expected]
    primary = max(expected_cards or cards, key=_rank)
    counted = [
        d
        for d in cards
        if d is primary
        or float(d.get("second_pass") or 0.0) >= SECOND_DOC_HIGH
        or _has_readable_fields(d)
    ]
    if len(counted) >= 2:
        return SideOutcome("reshoot", "multiple", None)
    if _cls(primary) != expected:
        return SideOutcome("reshoot", "wrong_side", None)
    result = _front_result(primary) if side == "front" else _back_result(primary)
    return SideOutcome("done", None, result)
