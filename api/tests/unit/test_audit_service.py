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


def test_otp_duration_allowed_but_otp_codes_still_dropped() -> None:
    """Feature 004: the OTP validity setting is audited; OTP codes never are (Principle II)."""
    from app.services.audit_service import _clean

    cleaned = _clean({"otp_validity_minutes": 30, "otp": "123456", "otp_code": "654321"})
    assert cleaned == {"otp_validity_minutes": 30}
