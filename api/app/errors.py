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
    "reading_not_retryable": "لا توجد قراءة فاشلة لإعادتها",
    "invalid_choice": "الاختيار غير صالح",
    "location_outside_iraq": "الموقع خارج العراق، تأكد من الإحداثيات",
    "image_too_large": "حجم الصورة أكبر من 5 ميغابايت",
    "invalid_image": "الملف ليس صورة صالحة",
    "image_too_big_dimensions": "أبعاد الصورة أكبر من المسموح، أعد اختيارها",
    "image_not_found": "الصورة غير موجودة",
    # Phone OTP (specs/007 contracts/api.md). Messages with minutes or attempts are built by
    # otp_service and passed as `message`; these are the plain forms.
    "otp_already_verified": "الرقم متحقق منه",
    "otp_resend_wait": "انتظر قبل إعادة الإرسال",
    "otp_hourly_limit": "وصلت الحد الأقصى (5 رموز في الساعة) لهذا الرقم، حاول لاحقاً",
    "otp_provider_busy": "خدمة الإرسال مشغولة، حاول بعد قليل",
    "otp_not_configured": "خدمة التحقق غير مهيّأة",
    "otp_no_credit": "تعذّر إرسال الرمز، أبلغ الإدارة",
    "otp_rejected": "تعذّر إرسال الرمز إلى هذا الرقم",
    "otp_unavailable": "تعذّر إرسال الرمز، حاول مرة أخرى",
    "otp_code_format": "الرمز 6 أرقام",
    "otp_wrong": "الرمز غير صحيح",
    "otp_cancelled": "أُلغي الرمز بعد 3 محاولات خاطئة، اطلب رمزاً جديداً",
    "otp_expired": "انتهت صلاحية الرمز، اطلب رمزاً جديداً",
    "otp_no_active": "لا يوجد رمز فعّال، اطلب رمزاً جديداً",
    # Check and decision at submission (specs/008 contracts/api.md)
    "phone_used": "المشترك موجود سابقاً، هل يود العودة للخدمة؟",
    "national_id_exists": "المشترك لديه اشتراك سابق",
    "no_family_match": "لا يوجد اشتراك سابق لهذه العائلة",
    # Existing subscriber paths (specs/009 contracts/api.md)
    "no_return_match": "لا يوجد اشتراك سابق لطلب العودة للخدمة",
    "return_pending": "يوجد طلب سابق بالانتظار لهذا المشترك",
    "draft_incomplete": "أكمل النواقص قبل الإرسال",
    "otp_needs_reverify": "يحتاج تحقق جديد",
    "catalog_changed": "تغيّرت الإعدادات، راجع الاشتراك وتحقق من الهاتف من جديد",
    "request_not_found": "الطلب غير موجود",
    # Admin review (specs/010 contracts/api.md)
    "already_decided": "تم البت في هذا الطلب مسبقاً",
    "warnings_unconfirmed": "يوجد تحذير على الطلب، أكّد القبول رغم التحذير",
    "commission_answer_required": "حدّد هل تُحتسب عمولة للمسوّق",
    "rejection_note_required": "اكتب سبب الرفض",
    "pin_source_empty": "لا توجد قيمة لهذا المصدر",
    "invalid_national_id": "الرقم الوطني يجب أن يكون 12 رقماً",
    "invalid_family_number": "الرقم العائلي غير صالح",
    # Subscriber deletion (specs/011 contracts/api.md)
    "request_deleted": "تم حذف هذا الطلب مسبقاً",
    "request_not_deletable": "لا يمكن حذف طلب مقبول أو مربوط",
    "number_mismatch": "رقم الطلب غير مطابق",
    # Statuses and notifications (specs/012 contracts/api.md)
    "invalid_transition": "لا يمكن تغيير حالة الطلب بهذا الشكل",
    "notification_not_found": "الإشعار غير موجود",
    # «تم الربط» and its undo (specs/013 contracts/api.md)
    "already_linked": "تم ربط هذا الطلب مسبقاً",
    "already_unlinked": "تم التراجع عن هذا الربط مسبقاً",
    # Legacy subscribers import (specs/014 contracts/api.md)
    "import_file_unreadable": "تعذّرت قراءة الملف، ارفع ملف xlsx أو csv",
    "import_columns_missing": "الملف ينقصه عمود",
    "import_too_many_rows": "الملف فيه أكثر من 2,000 صف",
    "import_file_too_large": "حجم الملف أكبر من 5 ميغابايت",
    "preview_not_found": "المعاينة غير موجودة أو انتهت، ارفع الملف من جديد",
    "preview_not_ready": "المعاينة لم تكتمل بعد",
    "preview_choices_missing": "بقيت صفوف بلا اختيار",
    "preview_changed": "تغيّرت البيانات منذ المعاينة، راجع الصفوف المعلّمة",
    "choice_not_allowed": "هذا الاختيار غير مسموح لهذا الصف",
    "tower_not_found": "البرج غير موجود",
    "wrong_current_password": "كلمة السر الحالية غير صحيحة",
    "weak_password": "كلمة السر يجب أن تكون 8 أحرف على الأقل",
    "same_password": "كلمة السر الجديدة يجب أن تختلف عن الحالية",
    "validation_error": "البيانات المدخلة غير صحيحة",
    "not_found": "الصفحة غير موجودة",
    "method_not_allowed": "العملية غير مسموحة",
    "server_error": "حدث خطأ غير متوقع، حاول مرة أخرى",
    "service_unavailable": "الخدمة غير متاحة حالياً",
}

# «فتح طلب برقمه» answers `request_not_found` with this message (specs/011 contracts/api.md).
NO_REQUEST_WITH_NUMBER = "لا يوجد طلب بهذا الرقم"


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
