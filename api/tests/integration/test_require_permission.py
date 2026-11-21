"""require_permission (specs/002 research R1, FR-003)."""

import pytest
from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, require_permission
from app.main import app
from tests.conftest import auth_header, login

_probe = APIRouter()


@_probe.get("/api/_test/needs-review-or-link")
def _needs(_: AuthContext = Depends(require_permission("review", "link"))) -> dict[str, bool]:
    return {"ok": True}


@pytest.fixture(scope="module", autouse=True)
def _mount_probe():
    app.include_router(_probe)
    yield
    app.router.routes[:] = [
        r for r in app.router.routes if getattr(r, "path", "") != "/api/_test/needs-review-or-link"
    ]


URL = "/api/_test/needs-review-or-link"


def test_super_admin_passes(client, make_user) -> None:
    u = make_user("super_admin")
    assert client.get(URL, headers=auth_header(login(client, u.phone))).status_code == 200


def test_marketer_refused(client, make_user) -> None:
    u = make_user("marketer")
    r = client.get(URL, headers=auth_header(login(client, u.phone)))
    assert r.status_code == 403
    assert r.json() == {"code": "forbidden", "message": "ليست لديك صلاحية"}


@pytest.mark.parametrize(
    ("perms", "status"),
    [
        ([], 403),
        (["marketers"], 403),
        (["review"], 200),
        (["link"], 200),
        (["link", "settings"], 200),
    ],
)
def test_admin_any_of(client, make_user, db, perms, status) -> None:
    u = make_user("admin")
    u.permissions = perms
    db.flush()
    assert client.get(URL, headers=auth_header(login(client, u.phone))).status_code == status


def test_permission_change_applies_on_next_request(client, make_user, db) -> None:
    u = make_user("admin")
    headers = auth_header(login(client, u.phone))
    assert client.get(URL, headers=headers).status_code == 403
    u.permissions = ["review"]
    db.flush()
    assert client.get(URL, headers=headers).status_code == 200  # same token, no new sign-in
    u.permissions = []
    db.flush()
    assert client.get(URL, headers=headers).status_code == 403
