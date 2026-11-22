"""Synthetic scenarios of the fake card reader (specs/006 research R10).

Each scenario is selected by the colour of the photo's top-left corner; the e2e helper and the
pytest helper draw plain images with that colour (and the words «بطاقة تجريبية»). All names and
numbers below are made up. `e2e/tests/fixtures/ocr-scenarios.json` is generated from this file
(`python -m app.services.card_reader_fake_data > …`).
"""

import json
from typing import Any

NID = "199912345678"
NID_OTHER = "199912345679"
DOC = "A12345678"
FAMILY = "1064L00M1234567890"

FRONT_FIELDS = {
    "name": "مشترك",
    "dad": "تجريبي",
    "gf": "اختبار",
    "last": "الوهمي",
    "mom": "أم",
    "gm": "تجريبية",
    "gn": "ذكر",
    "id": NID,
    "id2": DOC,
}

FRONT_FIELDS_B = {
    "name": "سالم",
    "dad": "كريم",
    "gf": "ناصر",
    "last": "التجريبي",
    "mom": "زينب",
    "gm": "علي",
    "gn": "ذكر",
    "id": NID,
    "id2": DOC,
}


def _front(fields: dict[str, str], box=(20, 20, 980, 620), second_pass=0.95) -> dict[str, Any]:
    return {
        "class": "iraq id card",
        "confidence": 0.95,
        "second_pass": second_pass,
        "box": list(box),
        "orientation": "NORMAL",
        "fields": {k: {"text": v, "confidence": 0.97} for k, v in fields.items()},
        "mrz": None,
        "error": None,
    }


def _zone(nid: str = NID, composite: bool | None = True) -> dict[str, Any]:
    return {
        "mrz_type": "TD1",
        "number": DOC,
        "optional1": nid + "<<<",
        "date_of_birth": "990101",
        "expiration_date": "300101",
        "sex": "M",
        "valid_number": True,
        "valid_date_of_birth": True,
        "valid_expiration_date": True,
        "valid_composite": composite,
    }


def _back(family: str | None = FAMILY, zone: dict | None = None, box=(20, 20, 980, 620)):
    fields = {"city": {"text": "مدينة تجريبية", "confidence": 0.93}}
    if family is not None:
        fields["nu_f"] = {"text": family, "confidence": 0.99}
    return {
        "class": "back",
        "confidence": 0.86,
        "second_pass": 0.85,
        "box": list(box),
        "orientation": "NORMAL",
        "fields": fields,
        "mrz": zone if zone is not None else _zone(),
        "error": None,
    }


# name → (corner colour RGB, detections | special behaviour)
SCENARIOS: dict[str, dict[str, Any]] = {
    "clear_front": {"rgb": [220, 40, 40], "detections": [_front(FRONT_FIELDS)]},
    "clear_back": {"rgb": [40, 160, 60], "detections": [_back()]},
    "front_b": {"rgb": [240, 140, 20], "detections": [_front(FRONT_FIELDS_B)]},
    "front_no_surname": {
        "rgb": [150, 40, 200],
        "detections": [_front({k: v for k, v in FRONT_FIELDS.items() if k != "last"})],
    },
    "front_no_id": {
        "rgb": [0, 150, 150],
        "detections": [_front({k: v for k, v in FRONT_FIELDS.items() if k != "id"})],
    },
    "front_latin_name": {
        "rgb": [200, 0, 120],
        "detections": [_front({**FRONT_FIELDS, "gf": "Test"})],
    },
    "back_nid_mismatch": {"rgb": [30, 60, 200], "detections": [_back(zone=_zone(NID_OTHER))]},
    "back_unverified": {
        "rgb": [200, 200, 40],
        "detections": [_back(zone=_zone(NID_OTHER, composite=None))],
    },
    "back_family_o": {"rgb": [255, 105, 180], "detections": [_back(family="1064LOOM1234567890")]},
    "no_card": {"rgb": [0, 255, 120], "detections": []},
    "two_cards": {
        "rgb": [0, 200, 255],
        "detections": [
            _front(FRONT_FIELDS),
            _front(FRONT_FIELDS_B, box=(1000, 20, 1900, 620)),
        ],
    },
    "duplicate_back": {
        "rgb": [100, 100, 255],
        "detections": [_back(family=None), _back(box=(30, 700, 990, 1290))],
    },
    "other_document": {
        "rgb": [255, 255, 0],
        "detections": [{**_front({}), "class": "drive", "confidence": 0.7, "second_pass": 0.7}],
    },
    "reader_failure": {"rgb": [80, 0, 160], "fail": "unavailable"},
    "reader_slow": {"rgb": [90, 0, 0], "slow": True},
}

# A photo whose corner is far from every scenario colour (a real photo in development) reads as
# the clear card of the slot it was uploaded to.
DEFAULT_FOR_SIDE = {"front": "clear_front", "back": "clear_back"}
MAX_COLOUR_DISTANCE = 40.0


def palette() -> dict[str, list[int]]:
    return {name: scenario["rgb"] for name, scenario in SCENARIOS.items()}


if __name__ == "__main__":
    print(json.dumps(palette(), ensure_ascii=False, indent=2))
