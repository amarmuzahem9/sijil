"""Read one photo with the upstream building blocks and return every detected document.

Contract: specs/006-card-ocr/contracts/ocr-service.md (POST /read). This module makes no
decision: it does not pair fronts and backs and rejects nothing (owner decision 3). The Sijil
app applies its own rules to the raw detections.

Privacy: nothing is written to disk and no field text is logged.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

log = logging.getLogger("ocr.reader")

FRONT_CLASS = "iraq id card"
BACK_CLASS = "back"
# Fields are read only for detections at or above upstream's second-pass threshold.
SECOND_PASS_MIN = 0.50

UPSTREAM_COMMIT = "c12a24e"


def _quiet_upstream_logs() -> None:
    """Upstream logs field labels and card ids at INFO; keep only warnings and errors."""
    for name in ("idcard_extractor", "ppocr", "paddle", "paddlex", "ultralytics"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _check_digit(data: str) -> str:
    """ICAO 9303 check digit (weights 7, 3, 1; '<' = 0; A = 10 … Z = 35)."""
    total = 0
    for i, char in enumerate(data):
        if char.isdigit():
            value = int(char)
        elif "A" <= char <= "Z":
            value = ord(char) - ord("A") + 10
        else:
            value = 0
        total += value * (7, 3, 1)[i % 3]
    return str(total % 10)


def _td1_lines(raw: str | None) -> tuple[str, str] | None:
    """Lines 1 and 2 of a TD1 zone, with dropped fillers put back.

    OCR often drops a few `<` fillers in the middle of line 2 (step 0, card 1: 28 characters).
    Line 2 ends with the composite check digit, and positions 18–28 are fillers on Iraqi cards,
    so the line is rebuilt as `line[:-1]` padded with `<` to 29 characters plus its last
    character. Fillers count as 0 in the check-digit sum, so this never makes wrong data pass.
    """
    if not raw:
        return None
    lines = [line.replace(" ", "").upper() for line in raw.split("\n") if line.strip()]
    if len(lines) < 2:
        return None
    l1, l2 = lines[0], lines[1]
    if len(l1) > 30 or len(l2) > 30 or len(l2) < 19:
        return None
    l1 = l1.ljust(30, "<")
    if len(l2) < 30:
        l2 = l2[:-1].ljust(29, "<") + l2[-1]
    return l1, l2


def composite_from_raw(raw_mrz: str | None) -> bool | None:
    """TD1 composite check digit from the raw lines (research R4), or None."""
    lines = _td1_lines(raw_mrz)
    if lines is None:
        return None
    l1, l2 = lines
    return _check_digit(l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29]) == l2[29]


def _mrz_out(mrz: dict[str, Any] | None) -> dict[str, Any] | None:
    if not mrz:
        return None
    composite = mrz.get("valid_composite")
    if composite is not True:
        # mrzmini gives `raw_text`; upstream's Tesseract fallback gives `raw_mrz`.
        recomputed = composite_from_raw(mrz.get("raw_text") or mrz.get("raw_mrz"))
        if recomputed is not None:
            composite = recomputed
    return {
        "mrz_type": mrz.get("mrz_type"),
        "number": mrz.get("number"),
        "optional1": mrz.get("optional1"),
        "date_of_birth": mrz.get("date_of_birth"),
        "expiration_date": mrz.get("expiration_date"),
        "sex": mrz.get("sex"),
        "valid_number": bool(mrz.get("valid_number")),
        "valid_date_of_birth": bool(mrz.get("valid_date_of_birth")),
        "valid_expiration_date": bool(mrz.get("valid_expiration_date")),
        "valid_composite": composite,
    }


@dataclass
class Models:
    settings: Any
    findcard: Any
    text: Any
    mrz: Any
    recognizer: Any


def load() -> Models:
    """Load the three detectors and the text recognizer once (about 8 s on 2 CPUs)."""
    from idcard_extractor.config import load_settings
    from idcard_extractor.detection.yolo_utils import load_yolo
    from idcard_extractor.ocr.text_reader import load_text_recognizer

    _quiet_upstream_logs()
    settings = load_settings()
    started = time.perf_counter()
    models = Models(
        settings=settings,
        findcard=load_yolo(settings.findcard_weights),
        text=load_yolo(settings.text_weights),
        mrz=load_yolo(settings.mrz_weights),
        recognizer=load_text_recognizer(settings.ocr_model_name, settings.ocr_device),
    )
    log.warning("models loaded in %.1f s", time.perf_counter() - started)
    return models


def decode(image_bytes: bytes) -> np.ndarray | None:
    data = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None


def _box(corners: np.ndarray) -> list[int]:
    xs, ys = corners[:, 0], corners[:, 1]
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _read_card(models: Models, card_image: np.ndarray, card_class: str) -> dict[str, Any]:
    """Orient one warped card and read its fields (and MRZ for a back)."""
    from idcard_extractor.detection.field_detector import detect_fields
    from idcard_extractor.detection.orientation import orient_back, orient_front
    from idcard_extractor.detection.yolo_utils import crop_detections
    from idcard_extractor.ocr.mrz_reader import read_mrz, split_mrz_crop
    from idcard_extractor.ocr.text_reader import recognize_fields

    s = models.settings
    cls = card_class.strip().lower()
    if cls == FRONT_CLASS:
        card, _, detections, orientation = orient_front(
            card_image,
            lambda c: detect_fields(c, models.text, s.detect_conf, s.yolo_device),
            s.orientation_margin,
        )
    elif cls == BACK_CLASS:
        card, _, detections, orientation = orient_back(
            card_image, lambda c: detect_fields(c, models.mrz, s.detect_conf, s.yolo_device)
        )
    else:
        return {"orientation": None, "fields": {}, "mrz": None}

    crops, mrz_crop = split_mrz_crop(crop_detections(card, detections))
    fields = recognize_fields(models.recognizer, crops)
    mrz = read_mrz(mrz_crop["crop"], s.tesseract_cmd) if mrz_crop is not None else None
    return {
        "orientation": (orientation or {}).get("decision"),
        "fields": {
            label: {"text": item.text, "confidence": round(float(item.confidence), 4)}
            for label, item in fields.items()
        },
        "mrz": _mrz_out(mrz),
    }


def read(models: Models, image: np.ndarray) -> dict[str, Any]:
    """Every document detected in `image`, read independently (contracts › POST /read)."""
    from idcard_extractor.detection.card_detector import detect_cards, second_pass_confidence

    s = models.settings
    started = time.perf_counter()
    out: list[dict[str, Any]] = []
    for detected in detect_cards(image, models.findcard, s.detect_conf, s.yolo_device):
        second = second_pass_confidence(
            detected.image, detected.card_class, models.findcard, s.detect_conf, s.yolo_device
        )
        item: dict[str, Any] = {
            "class": detected.card_class,
            "confidence": round(float(detected.confidence), 4),
            "second_pass": round(float(second), 4),
            "box": _box(detected.corners),
            "orientation": None,
            "fields": {},
            "mrz": None,
            "error": None,
        }
        if second >= SECOND_PASS_MIN:
            try:
                item.update(_read_card(models, detected.image, detected.card_class))
            except Exception as exc:  # one bad card must not fail the photo
                item["error"] = type(exc).__name__
                log.warning("reading a detection failed: %s", type(exc).__name__)
        out.append(item)
    return {"duration_ms": int((time.perf_counter() - started) * 1000), "detections": out}
