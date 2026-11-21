from app.services.audit_service import _clean


def test_secrets_are_dropped_but_flags_kept() -> None:
    cleaned = _clean(
        {
            "password": "x",
            "password_hash": "$argon2id$...",
            "refresh_token": "t",
            "otp_code": "123456",
            "jwt_secret": "s",
            "must_change_password": True,
            "name": "مستخدم",
        }
    )
    assert cleaned == {"must_change_password": True, "name": "مستخدم"}


def test_none_passthrough() -> None:
    assert _clean(None) is None
