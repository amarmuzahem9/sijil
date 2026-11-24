"""The allowed request status transitions (docs/system.md §7.2, specs/012 research R4).

`None` is the submission of a draft: a draft is not a request status (specs/008 research R1).
`link_service` (specs/013) calls `check` for «تم الربط» (approved → linked) and its undo
(linked → approved); the undo also checks that the request is linked, since pending → approved
is allowed here too.
A deleted request (011) is refused before this check, with `request_deleted`.
"""

from app.errors import AppError

TRANSITIONS: dict[str | None, frozenset[str]] = {
    None: frozenset({"approved", "pending_review"}),
    "pending_review": frozenset({"approved", "rejected"}),
    "approved": frozenset({"linked"}),
    "linked": frozenset({"approved"}),
}


def check(old: str | None, new: str) -> None:
    """Raise `invalid_transition` (409) unless §7.2 allows going from `old` to `new`."""
    if new not in TRANSITIONS.get(old, frozenset()):
        raise AppError("invalid_transition", 409)
