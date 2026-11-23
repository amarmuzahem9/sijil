"""What the check engine found (specs/008 research R2, specs/009 research R1, R2). No database.

A source reports one `MatchRecord` per existing subscriber record that matches the draft, saying
which of its keys matched. The views answer the §6.1 v1.10 questions: is it the same person
(national ID and family number on the same record), a conflict (national ID only), only the family,
or only the phone.
"""

from dataclasses import dataclass, field
from typing import Literal

ReturnBasis = Literal["identity", "phone"]


@dataclass(frozen=True)
class MatchRef:
    """One existing subscriber record: its source (`sijil`, later `legacy`, `sas`) and its id."""

    source: str
    ref_id: str


@dataclass(frozen=True)
class MatchRecord:
    """One matching record and which of the draft's keys it holds. `pending`: a request still
    waiting for review (it blocks a return, research R4)."""

    source: str
    ref_id: str
    phone: bool = False
    national_id: bool = False
    family: bool = False
    pending: bool = False

    @property
    def ref(self) -> MatchRef:
        return MatchRef(self.source, self.ref_id)


@dataclass
class Matches:
    records: list[MatchRecord] = field(default_factory=list)

    # --- views (research R1) ---

    @property
    def phone_records(self) -> list[MatchRecord]:
        return [r for r in self.records if r.phone]

    @property
    def same_person(self) -> list[MatchRecord]:
        return [r for r in self.records if r.national_id and r.family]

    @property
    def id_conflict(self) -> list[MatchRecord]:
        """National ID matches, family number differs or is missing on that record."""
        return [r for r in self.records if r.national_id and not r.family]

    @property
    def family_only(self) -> list[MatchRecord]:
        """Family number matches, national ID differs or is missing (a legacy record)."""
        return [r for r in self.records if r.family and not r.national_id]

    def return_target(self) -> tuple[ReturnBasis | None, list[MatchRecord]]:
        """Who a return would bring back (research R2): the same person by identity, else the
        phone's owner, else nobody."""
        if same := self.same_person:
            return "identity", same
        if phone := self.phone_records:
            return "phone", phone
        return None, []

    # --- 008 views: every record holding the key, as refs ---

    @property
    def phone(self) -> list[MatchRef]:
        return [r.ref for r in self.records if r.phone]

    @property
    def national_id(self) -> list[MatchRef]:
        return [r.ref for r in self.records if r.national_id]

    @property
    def family(self) -> list[MatchRef]:
        return [r.ref for r in self.records if r.family]

    @property
    def any(self) -> bool:
        return bool(self.records)

    def extend(self, other: "Matches") -> None:
        self.records.extend(other.records)
