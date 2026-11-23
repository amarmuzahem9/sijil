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
# Back of the card (owner change, research R13): born 1999-01-01, issued 2020-01-02, expires
# 2030-01-01 (= issue + 10 years - 1 day). The national ID starts with the birth year.
BIRTH = "1999/01/01"
ISSUE = "2020/01/02"
EXPIRY = "2030/01/01"
AUTHORITY = "مديرية الجنسية والمعلومات المدنية"
# A woman born after 2000 (owner request): the century comes from the national ID «20…».
NID_2005 = "200512345678"

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


def _zone(
    nid: str = NID,
    composite: bool | None = True,
    birth: str = "990101",
    expiry: str = "300101",
    birth_ok: bool = True,
    sex: str = "M",
) -> dict[str, Any]:
    return {
        "mrz_type": "TD1",
        "number": DOC,
        "optional1": nid + "<<<",
        "date_of_birth": birth,
        "expiration_date": expiry,
        "sex": sex,
        "valid_number": True,
        "valid_date_of_birth": birth_ok,
        "valid_expiration_date": True,
        "valid_composite": composite,
    }


def _bands(issue=(ISSUE, ISSUE), expiry=(EXPIRY,), birth=(BIRTH, BIRTH)) -> dict[str, Any]:
    """Printed rows as the reader returns them: candidate texts per row (research R13)."""
    return {
        "issue": list(issue),
        "expiry": list(expiry),
        "birth": list(birth),
        # A slightly misread authority, snapped to the known text by the app.
        "authority": {"text": "مديرية الجنسية والمعلومات المدنيه", "confidence": 0.93},
    }


def _back(
    family: str | None = FAMILY,
    zone: dict | None = None,
    box=(20, 20, 980, 620),
    bands: dict | None = None,
):
    fields = {"city": {"text": "حي تجريبي-بغداد", "confidence": 0.93}}
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
        "bands": bands if bands is not None else _bands(),
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
    # Back fields (owner change, research R13).
    "back_birth_print": {
        # MRZ birth check digit wrong; two printed readings agree on 1999-01-01.
        "rgb": [139, 69, 19],
        "detections": [
            _back(
                zone=_zone(birth="990107", birth_ok=False),
                bands=_bands(birth=(BIRTH, "1999/07/01", BIRTH)),
            )
        ],
    },
    "back_issue_mismatch": {
        "rgb": [128, 128, 0],
        "detections": [_back(bands=_bands(issue=("2021/05/05",)))],
    },
    "back_expired": {
        "rgb": [0, 0, 128],
        "detections": [
            _back(zone=_zone(expiry="250101"), bands=_bands(issue=("2015/01/02",), expiry=()))
        ],
    },
    "front_female_2000": {
        "rgb": [255, 180, 120],
        "detections": [_front({**FRONT_FIELDS, "name": "مشتركة", "gn": "أنثى", "id": NID_2005})],
    },
    "back_2000": {
        "rgb": [120, 200, 200],
        "detections": [
            _back(
                zone=_zone(nid=NID_2005, birth="050314", sex="F"),
                bands=_bands(birth=("2005/03/14", "2005/03/14")),
            )
        ],
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
