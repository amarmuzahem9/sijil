from tests.conftest import TEST_PASSWORD, auth_header, login


def test_login_success_body_and_cookie(client, make_user) -> None:
    user = make_user("marketer")
    r = login(client, user.phone)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 900 and body["access_token"]
    assert body["user"] == {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "role": "marketer",
        "permissions": [],
        "must_change_password": False,
    }
    cookie = r.headers["set-cookie"].lower()
    assert cookie.startswith("sijil_refresh=")
    for attr in ("httponly", "secure", "samesite=strict", "path=/api/auth", "max-age=2592000"):
        assert attr in cookie


def test_login_accepts_other_phone_formats(client, make_user) -> None:
    user = make_user(phone="07801234567")
    assert login(client, "+964 780 123 4567").status_code == 200
    arabic = "٠٧٨٠١٢٣٤٥٦٧"
    assert login(client, arabic).status_code == 200
    assert login(client, "‪07801234567‬").json()["user"]["id"] == user.id


def test_invalid_phone_is_422(client) -> None:
    r = login(client, "12345")
    assert r.status_code == 422
    assert r.json() == {"code": "invalid_phone", "message": "رقم غير صالح"}


def test_wrong_password_and_unknown_phone_are_identical(client, make_user) -> None:
    user = make_user()
    wrong = login(client, user.phone, "not-the-password")
    unknown = login(client, "07709999999", TEST_PASSWORD)
    assert wrong.status_code == unknown.status_code == 401
    assert (
        wrong.json()
        == unknown.json()
        == {
            "code": "invalid_credentials",
            "message": "رقم الهاتف أو كلمة السر غير صحيحة",
        }
    )
    assert "set-cookie" not in wrong.headers


def test_inactive_account_is_refused(client, make_user) -> None:
    user = make_user(is_active=False)
    r = login(client, user.phone)
    assert r.status_code == 403 and r.json()["code"] == "account_inactive"
    assert r.json()["message"] == "الحساب موقوف، راجع الإدارة"


def test_inactive_account_with_wrong_password_gets_generic_error(client, make_user) -> None:
    user = make_user(is_active=False)
    assert login(client, user.phone, "wrong-password").json()["code"] == "invalid_credentials"


def test_error_never_echoes_input(client) -> None:
    secret = "MySecretPassw0rd"
    r = login(client, "07709999998", secret)
    assert secret not in r.text and "07709999998" not in r.text


def test_refresh_rotates_cookie(client, make_user, frozen_clock) -> None:
    from datetime import timedelta

    user = make_user()
    first = login(client, user.phone)
    old_token = first.cookies["sijil_refresh"]

    r = client.post("/api/auth/refresh")
    assert r.status_code == 200 and r.json()["user"]["id"] == user.id
    new_token = r.cookies["sijil_refresh"]
    assert new_token and new_token != old_token

    # After the multi-tab grace window an already-rotated token is refused.
    frozen_clock.advance(timedelta(minutes=1))
    client.cookies.clear()
    client.cookies.set("sijil_refresh", old_token)
    stale = client.post("/api/auth/refresh")
    assert stale.status_code == 401 and stale.json()["code"] == "session_revoked"


def test_refresh_without_cookie(client) -> None:
    r = client.post("/api/auth/refresh")
    assert r.status_code == 401 and r.json()["code"] == "session_revoked"


def test_me(client, make_user) -> None:
    user = make_user("admin")
    r = client.get("/api/auth/me", headers=auth_header(login(client, user.phone)))
    assert r.status_code == 200 and r.json()["role"] == "admin"


def test_me_without_token(client) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["code"] == "not_authenticated"


def test_expired_access_token(client, make_user, frozen_clock) -> None:
    from datetime import timedelta

    user = make_user()
    headers = auth_header(login(client, user.phone))
    frozen_clock.advance(timedelta(minutes=16))
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 401 and r.json()["code"] == "token_expired"


def test_health(client) -> None:
    assert client.get("/api/health").json() == {"status": "ok", "db": "ok"}
