"""Account management rules (specs/002 data-model.md, research.md R3–R6).

Every change is audited: one entry per kind of change, none on a no-op. Routers stay thin and
call these functions; each function commits its own transaction.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access import normalize_permissions
from app.core.phone import normalize_phone
from app.core.security import hash_password
from app.core.timeutil import utc_now
from app.errors import AppError
from app.models import User
from app.services import audit_service
from app.services.auth_service import MIN_PASSWORD_LENGTH, deactivate_user_sessions

NAME_MIN, NAME_MAX = 2, 100


# --- validation ------------------------------------------------------------------------------


def clean_name(raw: str) -> str:
    name = " ".join(raw.split())  # trim and collapse inner whitespace
    if not NAME_MIN <= len(name) <= NAME_MAX:
        raise AppError("invalid_name", 422)
    return name


def clean_phone(raw: str) -> str:
    phone = normalize_phone(raw)
    if phone is None:
        raise AppError("invalid_phone", 422)
    return phone


def check_temporary_password(raw: str) -> str:
    if len(raw) < MIN_PASSWORD_LENGTH:
        raise AppError("weak_password", 422)
    return raw


def clean_permissions(raw: list[str]) -> list[str]:
    try:
        return normalize_permissions(raw)
    except ValueError as exc:
        raise AppError("validation_error", 422) from exc


def _ensure_phone_free(db: Session, phone: str, except_id: int | None = None) -> None:
    query = select(User.id).where(User.phone == phone)
    if except_id is not None:
        query = query.where(User.id != except_id)
    if db.execute(query).first() is not None:
        raise AppError("phone_taken", 409)


def _commit(db: Session) -> None:
    """Commit; a unique-phone race that slipped past the pre-check becomes phone_taken."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "users_phone_key" in str(exc.orig):
            raise AppError("phone_taken", 409) from exc
        raise


# --- targets ---------------------------------------------------------------------------------


def get_target(db: Session, user_id: int, role: str) -> User:
    """Only rows of the route's role are reachable: the main admin never is (research R4)."""
    user = db.get(User, user_id)
    if user is None or user.role != role:
        raise AppError("not_found", 404)
    return user


def ensure_not_protected(target: User) -> None:
    """Defence in depth: the main admin is never deactivated, reset or re-permissioned here."""
    if target.role == "super_admin":
        raise AppError("protected_account", 403)


def list_accounts(db: Session, role: str) -> list[User]:
    query = select(User).where(User.role == role)
    if role == "marketer":
        query = query.order_by(User.is_active.desc(), User.name)
    else:
        query = query.order_by(User.name)
    return list(db.execute(query).scalars())


# --- changes ---------------------------------------------------------------------------------


def create_account(
    db: Session,
    actor: User,
    *,
    role: str,
    name: str,
    phone: str,
    temporary_password: str,
    permissions: list[str] | None = None,
) -> User:
    if role not in ("admin", "marketer"):
        raise AppError("validation_error", 422)
    name = clean_name(name)
    phone = clean_phone(phone)
    check_temporary_password(temporary_password)
    perms = clean_permissions(permissions or []) if role == "admin" else []
    _ensure_phone_free(db, phone)

    user = User(
        name=name,
        phone=phone,
        password_hash=hash_password(temporary_password),
        role=role,
        permissions=perms,
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("phone_taken", 409) from exc
    audit_service.record(
        db,
        actor_id=actor.id,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        after={
            "name": user.name,
            "phone": user.phone,
            "role": user.role,
            "permissions": user.permissions,
            "is_active": True,
            "must_change_password": True,
        },
    )
    _commit(db)
    return user


def update_account(
    db: Session,
    actor: User,
    target: User,
    *,
    name: str | None = None,
    phone: str | None = None,
    permissions: list[str] | None = None,
) -> User:
    before: dict[str, object] = {}
    after: dict[str, object] = {}
    if name is not None:
        new_name = clean_name(name)
        if new_name != target.name:
            before["name"], after["name"] = target.name, new_name
    if phone is not None:
        new_phone = clean_phone(phone)
        if new_phone != target.phone:
            _ensure_phone_free(db, new_phone, except_id=target.id)
            before["phone"], after["phone"] = target.phone, new_phone

    new_perms: list[str] | None = None
    if permissions is not None:
        ensure_not_protected(target)
        if target.role != "admin":
            raise AppError("validation_error", 422)  # only admins hold permissions
        new_perms = clean_permissions(permissions)
        if new_perms == list(target.permissions):
            new_perms = None

    if not after and new_perms is None:
        return target  # no-op: nothing written

    now = utc_now()
    if after:
        if "name" in after:
            target.name = after["name"]  # type: ignore[assignment]
        if "phone" in after:
            target.phone = after["phone"]  # type: ignore[assignment]
        audit_service.record(
            db,
            actor_id=actor.id,
            action="user.updated",
            entity_type="user",
            entity_id=target.id,
            before=before,
            after=after,
        )
    if new_perms is not None:
        audit_service.record(
            db,
            actor_id=actor.id,
            action="user.permissions_changed",
            entity_type="user",
            entity_id=target.id,
            before={"permissions": list(target.permissions)},
            after={"permissions": new_perms},
        )
        target.permissions = new_perms
    target.updated_at = now
    _commit(db)
    return target


def set_active(db: Session, actor: User, target: User, active: bool) -> User:
    ensure_not_protected(target)
    if target.is_active == active:
        return target  # no-op
    target.is_active = active
    target.updated_at = utc_now()
    if not active:
        # Revoke too, so a later reactivation does not bring old devices back (research R3).
        deactivate_user_sessions(db, target.id, "deactivated")
    audit_service.record(
        db,
        actor_id=actor.id,
        action="user.reactivated" if active else "user.deactivated",
        entity_type="user",
        entity_id=target.id,
        before={"is_active": not active},
        after={"is_active": active},
    )
    _commit(db)
    return target


def reset_password(db: Session, actor: User, target: User, temporary_password: str) -> User:
    ensure_not_protected(target)
    check_temporary_password(temporary_password)
    was_forced = target.must_change_password
    target.password_hash = hash_password(temporary_password)
    target.must_change_password = True
    target.updated_at = utc_now()
    deactivate_user_sessions(db, target.id, "password_reset")
    audit_service.record(
        db,
        actor_id=actor.id,
        action="user.password_reset",
        entity_type="user",
        entity_id=target.id,
        before={"must_change_password": was_forced},
        after={"must_change_password": True},
    )
    _commit(db)
    return target
