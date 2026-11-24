"""Flags across rows and against stored data, and the allowed choices (specs/014 research R6).

Synthetic values only.
"""

from app.core import legacy_row as lr


def _row(index: int, **overrides) -> dict:
    raw = {
        "first_name": "سمير",
        "family_number": f"2222A00000000000{index:02d}",
        "phone": f"078222200{index:02d}",
        "front_image": f"https://drive.google.com/open?id=fake-ok-f-00{index:02d}",
        "back_image": f"https://drive.google.com/open?id=fake-ok-b-00{index:02d}",
        "legacy_number": f"T3C-{index:03d}",
        "status": "تم",
    }
    raw.update(overrides)
    row = lr.clean_row(index, raw)
    row["base_flags"] = row.pop("flags")
    row["images"] = {
        side: {"outcome": "ok" if row["drive_ids"][side] else "missing"}
        for side in ("front", "back")
    }
    return row


def _flags(rows, existing=None) -> dict[int, list[dict]]:
    result = lr.compute_flags(rows, existing or lr.Existing())
    return {row["index"]: row["flags"] for row in result}


def test_clean_rows_have_no_flags_and_may_be_imported() -> None:
    rows = lr.compute_flags([_row(2), _row(3)], lr.Existing())
    assert [r["flags"] for r in rows] == [[], []]
    assert [r["allowed"] for r in rows] == [["import", "skip"], ["import", "skip"]]


def test_repeats_in_the_file_by_family_key_and_phone() -> None:
    rows = [
        _row(2),
        _row(3, family_number="2222a00000000000o2"),  # same key as row 2
        _row(4, phone="+964 782 222 0002"),  # same phone as row 2
    ]
    flags = _flags(rows)
    assert flags[2] == [
        {"code": "family_dup_file", "rows": [3]},
        {"code": "phone_dup_file", "rows": [4]},
    ]
    assert flags[3] == [{"code": "family_dup_file", "rows": [2]}]
    assert flags[4] == [{"code": "phone_dup_file", "rows": [2]}]


def test_rows_not_counted_take_no_conflict_flags_and_give_none() -> None:
    rows = [_row(2), _row(3, phone="07822220002", status="ملغي"), _row(4, status="مرفوض")]
    existing = lr.Existing(sijil_phones={"07822220004": ["T3C-1001"]})
    flags = _flags(rows, existing)
    assert flags == {2: [], 3: [], 4: []}


def test_repeated_and_missing_legacy_numbers() -> None:
    rows = [_row(2), _row(3, legacy_number="T3C-002"), _row(4, legacy_number="؟")]
    flags = _flags(rows)
    assert flags[2] == [{"code": "legacy_number_dup_file", "rows": [3]}]
    assert flags[3] == [{"code": "legacy_number_dup_file", "rows": [2]}]
    assert flags[4] == [{"code": "legacy_number_missing"}]


def test_repeated_legacy_numbers_apply_to_rows_not_counted_too() -> None:
    flags = _flags([_row(2, status="ملغي"), _row(3, legacy_number="T3C-002", status="ملغي")])
    assert flags[2] == [{"code": "legacy_number_dup_file", "rows": [3]}]


def test_against_stored_legacy_subscribers_and_sijil_requests() -> None:
    existing = lr.Existing(
        legacy_numbers=frozenset({"T3C-005"}),
        legacy_phones=frozenset({"07822220002"}),
        legacy_family_keys=frozenset({"2222A0000000000003"}),
        sijil_phones={"07822220004": ["T3C-1004"]},
        sijil_family_keys={"2222A0000000000004": ["T3C-1004", "T3C-1007"]},
    )
    flags = _flags([_row(2), _row(3), _row(4), _row(5)], existing)
    assert flags[2] == [{"code": "phone_dup_legacy"}]
    assert flags[3] == [{"code": "family_dup_legacy"}]
    assert flags[4] == [{"code": "in_sijil", "requests": ["T3C-1004", "T3C-1007"]}]
    assert flags[5] == [{"code": "already_imported"}]


def test_already_imported_rows_are_left_out_of_file_repeats() -> None:
    existing = lr.Existing(legacy_numbers=frozenset({"T3C-002"}))
    rows = lr.compute_flags([_row(2), _row(3, family_number="2222A0000000000002")], existing)
    assert rows[0]["flags"] == [{"code": "already_imported"}]
    assert rows[0]["allowed"] == []
    assert rows[1]["flags"] == []


def test_image_outcomes_become_flags_after_the_row_flags() -> None:
    row = _row(2, front_image="")
    row["images"]["back"] = {"outcome": "not_shared"}
    assert _flags([row])[2] == [
        {"code": "image_missing", "side": "front"},
        {"code": "image_failed", "side": "back", "outcome": "not_shared"},
    ]


def test_allowed_choices_per_flag() -> None:
    assert lr.allowed_choices([{"code": "legacy_number_missing"}]) == ["skip"]
    assert lr.allowed_choices([{"code": "name_missing"}, {"code": "phone_invalid"}]) == ["skip"]
    assert lr.allowed_choices([{"code": "family_length"}]) == ["import", "skip", "correct"]
    assert lr.allowed_choices([{"code": "in_sijil", "requests": ["T3C-1001"]}]) == [
        "import",
        "skip",
    ]
    assert lr.allowed_choices([{"code": "already_imported"}]) == []
    assert lr.allowed_choices([]) == ["import", "skip"]


def test_compute_flags_does_not_change_its_input() -> None:
    rows = [_row(2), _row(3, family_number="2222A0000000000002")]
    before = [dict(r) for r in rows]
    lr.compute_flags(rows, lr.Existing())
    assert rows == before
