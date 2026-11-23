"""A complete, verified draft for the submission tests (specs/008 tasks T017–T031).

The card is read by the fake reader from synthetic images, so the names, national ID, family
number and back fields come «من البطاقة». The rest is typed. All values are made up.
"""

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.services.otp_sender import get_otp_sender
from tests.conftest import auth_header, login
from tests.helpers.card_images import scenario_jpeg

SETTINGS = "/api/admin/settings"
PHONE = "07801234567"


def marketer_headers(client: TestClient, user) -> dict[str, str]:
    headers = auth_header(login(client, user.phone))
    headers["X-Client-Id"] = str(uuid.uuid4())
    return headers


def make_catalog(client: TestClient, admin_headers: dict[str, str]) -> dict[str, Any]:
    def post(path: str, body: dict) -> dict:
        res = client.post(f"{SETTINGS}/{path}", json=body, headers=admin_headers)
        assert res.status_code == 201, res.json()
        return res.json()

    alam = post("areas", {"name": "العلم"})
    return {
        "alam": alam,
        "alm03": post("towers", {"code": "ALM03", "name": "برج 3", "area_id": alam["id"]}),
        "plus": post("plans", {"name": "PLUS", "trial_price": 20000, "second_price": 35000}),
    }


def get_draft(client, headers, draft_id: str) -> dict:
    res = client.get(f"/api/drafts/{draft_id}", headers=headers)
    assert res.status_code == 200, res.json()
    return res.json()


def patch(client, headers, draft_id: str, changes: dict, *, expect: int = 200) -> dict:
    version = get_draft(client, headers, draft_id)["version"]
    res = client.patch(
        f"/api/drafts/{draft_id}", json={"version": version, "changes": changes}, headers=headers
    )
    assert res.status_code == expect, res.json()
    return res.json()


def send_code(client, headers, draft_id: str):
    return client.post(f"/api/drafts/{draft_id}/otp/send", headers=headers)


def verify(client, headers, draft_id: str) -> dict:
    res = send_code(client, headers, draft_id)
    assert res.status_code == 200, res.json()
    code = get_otp_sender().outbox[-1][1]
    res = client.post(f"/api/drafts/{draft_id}/otp/verify", json={"code": code}, headers=headers)
    assert res.status_code == 200, res.json()
    assert res.json()["otp"]["status"] == "verified"
    return res.json()


def complete_draft(
    client: TestClient,
    headers: dict[str, str],
    catalog: dict[str, Any],
    *,
    phone: str = PHONE,
    read_card: bool = True,
    changes: dict | None = None,
    verified: bool = True,
) -> str:
    """A draft with nothing missing. `read_card=False` types every card field by hand."""
    draft_id = str(uuid.uuid4())
    res = client.put(f"/api/drafts/{draft_id}", json={"changes": {}}, headers=headers)
    assert res.status_code == 201, res.json()
    for side, scenario in (("front", "clear_front"), ("back", "clear_back")):
        # Without a reading the images are still required; a no-card photo reads nothing.
        name = scenario if read_card else "no_card"
        res = client.post(
            f"/api/drafts/{draft_id}/images/{side}",
            files={"file": (f"{side}.jpg", scenario_jpeg(name), "image/jpeg")},
            headers=headers,
        )
        assert res.status_code == 200, res.text
    typed: dict[str, Any] = {
        "great_grandfather_name": "مثال",
        "location": {"lat": 34.70, "lng": 43.68, "source": "gps", "accuracy_m": 8},
        "address": "حي تجريبي",
        "landmark": "قرب نقطة تجريبية",
        "area_id": catalog["alam"]["id"],
        "tower_id": catalog["alm03"]["id"],
        "plan_id": catalog["plus"]["id"],
        "phone_input": phone,
    }
    if not read_card:
        typed |= {
            "first_name": "تجربة",
            "father_name": "اختبار",
            "grandfather_name": "نموذج",
            "surname": "التجريبي",
            "mother_first_name": "عينة",
            "mother_second_name": "نموذجية",
            "national_id": "199955556666",
            "family_number": "2222B0000000000001",
            "birth_date": "1999-05-05",
            "birth_place": "بغداد",
            "issue_date": "2021-03-03",
            "expiry_date": "2031-03-02",
            "issuing_authority": "مديرية الجنسية والمعلومات المدنية",
        }
    typed |= changes or {}
    out = patch(client, headers, draft_id, typed)
    if verified:
        out = verify(client, headers, draft_id)
        assert out["missing"] == [], out["missing"]
    return draft_id


def submit(client, headers, draft_id: str, version: int | None = None):
    if version is None:
        version = get_draft(client, headers, draft_id)["version"]
    return client.post(f"/api/drafts/{draft_id}/submit", json={"version": version}, headers=headers)
