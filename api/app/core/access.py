"""Admin page → permission map (docs/system.md §10 v1.1, specs/002 data-model.md).

Mirrored in web/src/auth/access.ts; both are tested against tests/fixtures/page_access.json.
"""

from collections.abc import Iterable
from typing import Literal

ADMIN_PERMISSIONS: tuple[str, ...] = (
    "review",
    "link",
    "settings",
    "marketers",
    "reports",
    "commissions",
    # «حذف مشترك»: erase a pending or rejected request (system.md v1.15 §7.4, specs/011 R7).
    "delete",
)

AccessRule = Literal["any_admin", "super_admin"] | tuple[str, ...]

PAGE_ACCESS: dict[str, AccessRule] = {
    "home": "any_admin",
    "pending": ("review",),
    "awaiting_link": ("link",),
    "subscribers": ("review", "link", "reports"),
    "marketers": ("marketers",),
    "settings": ("settings",),
    "admins": "super_admin",
    "reports": ("reports",),
    "import": ("reports",),
    "backup": "super_admin",
    "audit": "super_admin",
    "archive": "super_admin",
    "account": "any_admin",
}


def has_any_permission(role: str, permissions: Iterable[str], required: Iterable[str]) -> bool:
    """The main admin holds every permission implicitly; marketers hold none."""
    if role == "super_admin":
        return True
    if role != "admin":
        return False
    return bool(set(permissions) & set(required))


def can_access(role: str, permissions: Iterable[str], page: str) -> bool:
    rule = PAGE_ACCESS[page]
    if role not in ("super_admin", "admin"):
        return False
    if rule == "any_admin":
        return True
    if rule == "super_admin":
        return role == "super_admin"
    return has_any_permission(role, permissions, rule)


def normalize_permissions(values: Iterable[str]) -> list[str]:
    """Deduplicate and order canonically. Raises ValueError on an unknown key."""
    wanted = set(values)
    unknown = wanted - set(ADMIN_PERMISSIONS)
    if unknown:
        raise ValueError("unknown permission")
    return [p for p in ADMIN_PERMISSIONS if p in wanted]
