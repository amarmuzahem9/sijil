"""The audit viewer names settings items even when an entry stores only the changed field."""

from tests.conftest import auth_header, login

BASE = "/api/admin/settings"


def test_target_label_for_settings_entries(client, make_user) -> None:
    h = auth_header(login(client, make_user("super_admin").phone))
    area = client.post(f"{BASE}/areas", json={"name": "العلم"}, headers=h).json()
    tower = client.post(
        f"{BASE}/towers",
        json={"code": "ALM01", "name": "العلم 1", "area_id": area["id"]},
        headers=h,
    ).json()
    temp = client.post(f"{BASE}/areas", json={"name": "منطقة مؤقتة"}, headers=h).json()
    client.post(f"{BASE}/towers/{tower['id']}/deactivate", headers=h)  # stores {is_active} only
    client.delete(f"{BASE}/areas/{temp['id']}", headers=h)  # row gone: label from `before`

    items = client.get("/api/admin/audit", headers=h).json()["items"]
    by_action = {(i["action"], i["entity_id"]): i for i in items}
    deactivated = by_action[("tower.deactivated", str(tower["id"]))]
    assert deactivated["target_label"] == "ALM01" and deactivated["target"] is None
    assert by_action[("area.deleted", str(temp["id"]))]["target_label"] == "منطقة مؤقتة"
    assert by_action[("area.created", str(area["id"]))]["target_label"] == "العلم"
    user_entries = [i for i in items if i["entity_type"] == "user"]
    assert all(i["target_label"] is None for i in user_entries)
