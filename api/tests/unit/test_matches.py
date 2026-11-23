"""Matches per record and their views (specs/009 research R1, R2)."""

from app.core.matches import Matches, MatchRecord, MatchRef


def _rec(ref: str, *, phone=False, nid=False, family=False, pending=False) -> MatchRecord:
    return MatchRecord("sijil", ref, phone=phone, national_id=nid, family=family, pending=pending)


def test_record_with_every_flag_is_same_person_and_phone() -> None:
    a = _rec("1", phone=True, nid=True, family=True)
    m = Matches([a])
    assert m.phone_records == [a]
    assert m.same_person == [a]
    assert m.id_conflict == []
    assert m.family_only == []


def test_national_id_without_family_is_a_conflict() -> None:
    a = _rec("1", nid=True)
    m = Matches([a])
    assert m.same_person == []
    assert m.id_conflict == [a]


def test_family_without_national_id_is_family_only() -> None:
    a = _rec("1", family=True)
    m = Matches([a])
    assert m.family_only == [a]
    assert m.same_person == [] and m.id_conflict == []


def test_old_views_keep_every_match_as_refs() -> None:
    a = _rec("1", nid=True, family=True)
    b = _rec("2", family=True)
    m = Matches([a, b])
    assert m.national_id == [MatchRef("sijil", "1")]
    assert m.family == [MatchRef("sijil", "1"), MatchRef("sijil", "2")]
    assert m.phone == []
    assert m.any


def test_identity_target_wins_over_phone() -> None:
    a = _rec("A", phone=True)
    b = _rec("B", nid=True, family=True)
    basis, target = Matches([a, b]).return_target()
    assert basis == "identity"
    assert target == [b]


def test_phone_only_target_is_the_phone_records() -> None:
    a = _rec("A", phone=True)
    basis, target = Matches([a]).return_target()
    assert (basis, target) == ("phone", [a])


def test_no_match_no_target() -> None:
    assert Matches().return_target() == (None, [])
    assert not Matches().any


def test_conflict_or_family_alone_gives_no_target() -> None:
    m = Matches([_rec("1", nid=True), _rec("2", family=True)])
    assert m.return_target() == (None, [])


def test_extend_appends_records() -> None:
    m = Matches([_rec("1", phone=True)])
    m.extend(Matches([_rec("2", family=True)]))
    assert [r.ref_id for r in m.records] == ["1", "2"]


def test_record_ref() -> None:
    assert _rec("9").ref == MatchRef("sijil", "9")
