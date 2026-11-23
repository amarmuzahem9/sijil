"""require_permission (specs/002 research R1, FR-003)."""

import uuid

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


# --- specs/010 T057 (SC-006): every review route needs `review`; the home counts do not ---

_REVIEW_ROUTES = [
    ("get", "/api/admin/requests/pending", None, 403),
    ("get", "/api/admin/requests/{id}", None, 404),
    ("post", "/api/admin/requests/{id}/accept", {}, 404),
    ("post", "/api/admin/requests/{id}/reject", {"reason": "card_unclear"}, 404),
    ("post", "/api/admin/requests/{id}/pin", {"field": "national_id", "source": "marketer"}, 404),
    ("get", "/api/admin/request-images/{image}", None, 404),
]


@pytest.mark.parametrize(
    "perms", [[], ["settings"], ["link", "marketers", "reports", "commissions"]]
)
@pytest.mark.parametrize(("method", "path", "body", "status"), _REVIEW_ROUTES)
def test_review_routes_need_review(
    client, make_user, db, perms, method, path, body, status
) -> None:
    from app.models import Request
    from tests.helpers.requests import request_factory

    request = request_factory(db, make_user("marketer"), status="pending_review")
    url = path.format(id=request.id, image=uuid.uuid4())
    admin = make_user("admin")
    admin.permissions = perms
    db.flush()

    h = auth_header(login(client, admin.phone))
    res = getattr(client, method)(url, headers=h, **({"json": body} if body is not None else {}))

    assert res.status_code == status
    db.expire_all()
    assert db.get(Request, request.id).status == "pending_review"


def test_the_home_counts_are_open_to_every_admin(client, make_user, db) -> None:
    for perms in ([], ["settings"]):
        admin = make_user("admin")
        admin.permissions = perms
        db.flush()
        res = client.get("/api/admin/home", headers=auth_header(login(client, admin.phone)))
        assert res.status_code == 200
