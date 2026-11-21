"""/api/auth/* — contracts/api.md."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, current_user_allow_password_change
from app.config import get_settings
from app.db import get_db
from app.errors import AppError, error_response
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse
from app.schemas.user import UserOut
from app.services import auth_service

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
    result = auth_service.login(db, body.phone, body.password, request.headers.get("user-agent"))
    _set_refresh_cookie(response, result.refresh_token)
    return _token_body(result)


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
