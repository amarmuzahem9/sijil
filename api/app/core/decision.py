"""The §6.1 decision table (docs/system.md v1.10) as a pure function (specs/008 research R2,
specs/009 research R4).

Without a return choice, in order: 1 phone used and 2 same person (national ID and family number on
one record) refuse the request as new; 2b conflict (national ID only), 3 family and 4 numbers edited
add up as pending reasons; 5 (nothing) approves at once.

With a valid return choice: a pending record in the target refuses (`return_pending`), a phone
held by a record outside the target refuses (`phone_used`); otherwise a pending `return` request,
with the conflict, family and edited reasons that apply outside the target.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.core.matches import Matches, MatchRecord, MatchRef, ReturnBasis

Refusal = Literal["phone_used", "national_id_exists", "draft_incomplete", "return_pending"]
Result = Literal["approved", "pending_family", "pending_review", "pending_approval"]
ReasonCode = Literal["family_exists", "numbers_edited", "return", "numbers_conflict"]


@dataclass(frozen=True)
class Reason:
    reason: ReasonCode
    matches: list[MatchRef] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    basis: ReturnBasis | None = None


@dataclass(frozen=True)
class Decision:
    refusal: Refusal | None
    type: Literal["new", "additional", "return"] | None
    status: Literal["approved", "pending_review"] | None
    reasons: list[Reason]
    result: Result | None


def _refuse(code: Refusal) -> Decision:
    return Decision(refusal=code, type=None, status=None, reasons=[], result=None)


def _refs(records: list[MatchRecord]) -> list[MatchRef]:
    return [r.ref for r in records]


def decide(
    matches: Matches,
    edited_fields: list[str],
    additional_confirmed: bool,
    return_valid: bool = False,
) -> Decision:
    basis, target = matches.return_target()
    if return_valid and target:
        return _decide_return(matches, edited_fields, basis, target)

    if matches.phone_records:
        return _refuse("phone_used")
    if matches.same_person:
        return _refuse("national_id_exists")
    reasons: list[Reason] = []
    if conflict := matches.id_conflict:
        reasons.append(Reason("numbers_conflict", matches=_refs(conflict)))
    family = matches.family_only
    if family:
        if not additional_confirmed:
            # A missing item on the page; refused here too in case a call skips the page.
            return _refuse("draft_incomplete")
        reasons.append(Reason("family_exists", matches=_refs(family)))
    if edited_fields:
        reasons.append(Reason("numbers_edited", fields=list(edited_fields)))
    if not reasons:
        return Decision(None, "new", "approved", [], "approved")
    if family:
        result: Result = "pending_family"
    elif conflict:
        result = "pending_approval"
    else:
        result = "pending_review"
    return Decision(None, "additional" if family else "new", "pending_review", reasons, result)


def _decide_return(
    matches: Matches,
    edited_fields: list[str],
    basis: ReturnBasis | None,
    target: list[MatchRecord],
) -> Decision:
    if any(r.pending for r in target):
        return _refuse("return_pending")
    in_target = {r.ref for r in target}
    if any(r.ref not in in_target for r in matches.phone_records):
        return _refuse("phone_used")
    reasons = [Reason("return", matches=_refs(target), basis=basis)]
    if conflict := [r for r in matches.id_conflict if r.ref not in in_target]:
        reasons.append(Reason("numbers_conflict", matches=_refs(conflict)))
    if family := [r for r in matches.family_only if r.ref not in in_target]:
        reasons.append(Reason("family_exists", matches=_refs(family)))
    if edited_fields:
        reasons.append(Reason("numbers_edited", fields=list(edited_fields)))
    return Decision(None, "return", "pending_review", reasons, "pending_approval")
