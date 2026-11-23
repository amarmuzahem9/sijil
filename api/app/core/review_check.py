"""The re-check of a pending request during review (docs/system.md v1.14 §6.4, specs/010 research
R5). Pure: the caller passes the current matches (from match_service, the request itself removed).

Used after a pin (to mark the reasons and maybe turn `new` into `additional`), on every read of the
request file (to show the warnings) and at accept (to compare the warnings the admin confirmed).

- Reason rows that apply now: `numbers_conflict` and `family_exists`, one per record outside the
  return target. `return` rows are never recomputed; a lost target is a warning instead.
- The type changes only from `new` to `additional`, when a family-only record exists (FR-015).
- Warnings (FR-019a), in this order:
  `same_person`: a new or additional request matches a record on both numbers;
  `id_conflict`: a national-ID-only record that was not on the request before the pin;
  `return_target_lost`: an identity return whose target records no longer match on both numbers.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.core.matches import Matches, MatchRef, ReturnBasis

ReviewWarning = Literal["same_person", "id_conflict", "return_target_lost"]
RowReason = Literal["numbers_conflict", "family_exists"]

WARNING_ORDER: tuple[ReviewWarning, ...] = ("same_person", "id_conflict", "return_target_lost")


@dataclass(frozen=True)
class ReviewCheck:
    """specs/010 data-model.md › ReviewCheck."""

    open_rows: list[tuple[RowReason, MatchRef]] = field(default_factory=list)
    new_type: str = "new"
    warnings: list[ReviewWarning] = field(default_factory=list)


def review(
    type_: str,
    return_refs: list[MatchRef],
    return_basis: ReturnBasis | None,
    matches: Matches,
    prior_conflict_refs: set[MatchRef],
) -> ReviewCheck:
    target = set(return_refs) if type_ == "return" else set()

    conflict = [r.ref for r in matches.id_conflict if r.ref not in target]
    family = [r.ref for r in matches.family_only if r.ref not in target]
    rows: list[tuple[RowReason, MatchRef]] = [("numbers_conflict", r) for r in conflict]
    rows += [("family_exists", r) for r in family]

    new_type = "additional" if type_ == "new" and family else type_

    found: set[ReviewWarning] = set()
    if type_ in ("new", "additional") and matches.same_person:
        found.add("same_person")
    if any(r not in prior_conflict_refs for r in conflict):
        found.add("id_conflict")
    if type_ == "return" and return_basis == "identity":
        same = {r.ref for r in matches.same_person}
        if any(r not in same for r in target):
            found.add("return_target_lost")

    return ReviewCheck(
        open_rows=rows,
        new_type=new_type,
        warnings=[w for w in WARNING_ORDER if w in found],
    )
