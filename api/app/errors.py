"""Uniform error responses: {"code": "...", "message": "<Arabic>"} — never echo user input."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("sijil.errors")

MESSAGES: dict[str, str] = {
    "invalid_phone": "رقم غير صالح",
    "invalid_credentials": "رقم الهاتف أو كلمة السر غير صحيحة",
    "account_inactive": "الحساب موقوف، راجع الإدارة",
    "account_locked": "تم إيقاف الدخول مؤقتاً بسبب محاولات خاطئة متكررة",
    "too_many_attempts": "محاولات كثيرة، انتظر قليلاً ثم حاول مرة أخرى",
    "not_authenticated": "يجب تسجيل الدخول",
    "token_expired": "انتهت صلاحية الجلسة، يتم التجديد",
    "session_revoked": "انتهت الجلسة، سجّل الدخول مرة أخرى",
    "password_change_required": "يجب تغيير كلمة السر قبل المتابعة",
    "forbidden": "ليست لديك صلاحية",
    "protected_account": "لا يمكن تعديل حساب الأدمن الرئيسي",
    "phone_taken": "رقم الهاتف مستخدم لحساب آخر",
    "invalid_name": "الاسم يجب أن يكون بين 2 و100 حرف",
    # Settings (specs/004 contracts/api.md)
    "name_taken": "الاسم مستخدم",
    "invalid_code": "الرمز أحرف إنجليزية كبيرة وأرقام فقط",
    "code_taken": "رمز البرج مستخدم",
    "code_locked": "لا يمكن تغيير رمز برج مستعمل",
    "area_inactive": "المنطقة موقوفة",
    "invalid_amount": "المبلغ يجب أن يكون عدداً صحيحاً من 0 إلى 10,000,000",
    "invalid_tiers": "قائمة الشرائح غير صحيحة",
    "invalid_otp_minutes": "المدة يجب أن تكون من 5 إلى 1,440 دقيقة",
    "item_in_use": "العنصر مستعمل، يمكن إيقافه فقط",
    # Drafts and card images (specs/005 contracts/api.md)
    "draft_not_found": "المسودة غير موجودة",
    "draft_conflict": "تغيّرت المسودة من جهاز آخر",
    "too_long": "النص أطول من المسموح",
    "invalid_name_text": "الاسم أحرف عربية فقط",
    "invalid_place_text": "محل الولادة أحرف عربية فقط",
    "invalid_choice": "الاختيار غير صالح",
    "location_outside_iraq": "الموقع خارج العراق، تأكد من الإحداثيات",
    "image_too_large": "حجم الصورة أكبر من 5 ميغابايت",
    "invalid_image": "الملف ليس صورة صالحة",
    "image_too_big_dimensions": "أبعاد الصورة أكبر من المسموح، أعد اختيارها",
    "image_not_found": "الصورة غير موجودة",
    "wrong_current_password": "كلمة السر الحالية غير صحيحة",
    "weak_password": "كلمة السر يجب أن تكون 8 أحرف على الأقل",
    "same_password": "كلمة السر الجديدة يجب أن تختلف عن الحالية",
    "validation_error": "البيانات المدخلة غير صحيحة",
    "not_found": "الصفحة غير موجودة",
    "method_not_allowed": "العملية غير مسموحة",
    "server_error": "حدث خطأ غير متوقع، حاول مرة أخرى",
    "service_unavailable": "الخدمة غير متاحة حالياً",
}


class AppError(Exception):
    def __init__(
        self,
        code: str,
        status: int,
        message: str | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.message = message or MESSAGES[code]
        self.headers = headers
        self.extra = extra or {}


def error_response(err: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=err.status,
        content={"code": err.code, "message": err.message, **err.extra},
        headers=err.headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, __: RequestValidationError) -> JSONResponse:
        # Deliberately generic: validation details would echo the submitted values.
        return error_response(AppError("validation_error", 422))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "server_error")
        return error_response(AppError(code, exc.status_code))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.error(
            "unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__
        )
        return error_response(AppError("server_error", 500))
