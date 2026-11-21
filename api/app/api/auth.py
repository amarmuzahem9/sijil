"""/api/auth/* — contracts/api.md."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, current_user, current_user_allow_password_change
from app.config import get_settings
from app.core.ratelimit import login_failures
from app.db import get_db
from app.errors import AppError, error_response
from app.schemas.accounts import NameUpdate
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse
from app.schemas.user import UserOut
from app.services import account_service, auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "sijil_refresh"
REFRESH_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


def _token_body(result: auth_service.AuthResult) -> TokenResponse:
    return TokenResponse(
        access_token=result.access_token,
        expires_in=get_settings().access_token_minutes * 60,
        user=UserOut.model_validate(result.user),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    settings = get_settings()
    # request.client is the real client: uvicorn applies X-Forwarded-For only from trusted proxies.
    client_ip = request.client.host if request.client else "unknown"
    window = timedelta(minutes=settings.login_ip_window_minutes)
    wait = login_failures.retry_after(client_ip, settings.login_ip_limit, window)
    if wait is not None:
        raise AppError(
            "too_many_attempts",
            429,
            headers={"Retry-After": str(wait)},
            extra={"retry_after_seconds": wait},
        )
    try:
        result = auth_service.login(
            db, body.phone, body.password, request.headers.get("user-agent")
        )
    except AppError as err:
        if err.code in ("invalid_credentials", "account_locked"):
            login_failures.record_failure(client_ip)
        raise
    _set_refresh_cookie(response, result.refresh_token)
    return _token_body(result)


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    """Ends only this device's session; always 204 (contracts/api.md)."""
    auth_service.logout(db, request.cookies.get(REFRESH_COOKIE))
    response = Response(status_code=204)
    _clear_refresh_cookie(response)
    return response


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        result = auth_service.refresh(db, request.cookies.get(REFRESH_COOKIE))
    except AppError as err:
        failed = error_response(err)
        _clear_refresh_cookie(failed)
        return failed
    _set_refresh_cookie(response, result.refresh_token)
    return _token_body(result)


@router.get("/me", response_model=UserOut)
def me(ctx: AuthContext = Depends(current_user_allow_password_change)) -> UserOut:
    return UserOut.model_validate(ctx.user)


@router.patch("/me", response_model=UserOut)
def update_me(
    body: NameUpdate, ctx: AuthContext = Depends(current_user), db: Session = Depends(get_db)
) -> UserOut:
    """Only the main admin may rename themselves; nobody edits their own phone (system.md §3.5)."""
    if ctx.user.role != "super_admin":
        raise AppError("forbidden", 403)
    user = account_service.update_account(db, ctx.user, ctx.user, name=body.name)
    return UserOut.model_validate(user)


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    body: ChangePasswordRequest,
    response: Response,
    ctx: AuthContext = Depends(current_user_allow_password_change),
    db: Session = Depends(get_db),
) -> TokenResponse:
    result = auth_service.change_password(
        db, ctx.user, ctx.session, body.current_password, body.new_password
    )
    _set_refresh_cookie(response, result.refresh_token)
    return _token_body(result)
