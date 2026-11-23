"""What the check engine found (specs/008 research R2). Plain values, no database."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MatchRef:
    """One existing subscriber record: its source (`sijil`, later `legacy`, `sas`) and its id."""

    source: str
    ref_id: str


@dataclass
class Matches:
    phone: list[MatchRef] = field(default_factory=list)
    national_id: list[MatchRef] = field(default_factory=list)
    family: list[MatchRef] = field(default_factory=list)

    @property
    def any(self) -> bool:
        return bool(self.phone or self.national_id or self.family)

    def extend(self, other: "Matches") -> None:
        self.phone.extend(other.phone)
        self.national_id.extend(other.national_id)
        self.family.extend(other.family)
