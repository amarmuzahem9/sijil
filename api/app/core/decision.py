"""The §6.1 decision table as a pure function (specs/008 research R2).

Rows in order: 1 phone used and 2 national ID exists refuse the request as new; 3 family exists
and 4 numbers edited add up as pending reasons; 5 (nothing) approves at once.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.core.matches import Matches, MatchRef

Refusal = Literal["phone_used", "national_id_exists", "draft_incomplete"]
Result = Literal["approved", "pending_family", "pending_review"]


@dataclass(frozen=True)
class Reason:
    reason: Literal["family_exists", "numbers_edited"]
    matches: list[MatchRef] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Decision:
    refusal: Refusal | None
    type: Literal["new", "additional"] | None
    status: Literal["approved", "pending_review"] | None
    reasons: list[Reason]
    result: Result | None


def _refuse(code: Refusal) -> Decision:
    return Decision(refusal=code, type=None, status=None, reasons=[], result=None)


def decide(matches: Matches, edited_fields: list[str], additional_confirmed: bool) -> Decision:
    if matches.phone:
        return _refuse("phone_used")
    if matches.national_id:
        return _refuse("national_id_exists")
    reasons: list[Reason] = []
    if matches.family:
        if not additional_confirmed:
            # A missing item on the page; refused here too in case a call skips the page.
            return _refuse("draft_incomplete")
        reasons.append(Reason("family_exists", matches=list(matches.family)))
    if edited_fields:
        reasons.append(Reason("numbers_edited", fields=list(edited_fields)))
    if not reasons:
        return Decision(None, "new", "approved", [], "approved")
    family = bool(matches.family)
    return Decision(
        None,
        "additional" if family else "new",
        "pending_review",
        reasons,
        "pending_family" if family else "pending_review",
    )
