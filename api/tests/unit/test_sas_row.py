"""Pure rules of one SAS file row (specs/015 research R2–R7, R9). Synthetic values only."""

from datetime import UTC, datetime

import pytest

from app.core import sas_row
from app.core.sas_row import Existing

HEADERS = [
    "id",
    "username",
    "firstname",
    "lastname",
    "phone",
    "expiration",
    "notes",
    "parent_name",
    "ct_password",
    "created_at",
    "last_online",
    "group_name",
]


# --- headers (R2, R3) ---------------------------------------------------------------------------


def test_headers_map_known_columns_and_never_a_password() -> None:
    found = sas_row.match_headers(HEADERS)
    assert found["username"] == 1
    assert found["phone"] == 4
    assert found["sas_id"] == 0
    assert found["group_name"] == 11
    assert 8 not in found.values()  # ct_password


@pytest.mark.parametrize(
    "header", ["ct_password", "CT_Password", " ct_password ", "password", "user_PASSWORD_hash"]
)
def test_any_password_header_is_never_mapped(header: str) -> None:
    found = sas_row.match_headers(["username", "phone", header])
    assert set(found) == {"username", "phone"}


def test_headers_ignore_case_spaces_and_unknown_columns() -> None:
    found = sas_row.match_headers([" UserName ", "PHONE", "something_else"])
    assert found == {"username": 0, "phone": 1}


def test_missing_required_columns_are_named() -> None:
    with pytest.raises(sas_row.MissingColumns) as missing:
        sas_row.match_headers(["id", "firstname"])
    assert missing.value.columns == ["username", "phone"]


# --- username split and tower code (R4) ---------------------------------------------------------


@pytest.mark.parametrize(
    ("username", "prefix", "phone"),
    [
        ("ALM03-07801234567", "ALM03", "07801234567"),
        ("RBD-01S-7801234567", "RBD-01S", "07801234567"),
        ("smr-01-07801234567", "SMR-01", "07801234567"),
        ("KZF06-٠٧٨٠١٢٣٤٥٦٧", "KZF06", "07801234567"),
        ("abc", None, None),
        ("ALM03-123", None, None),
        ("07801234567", None, "07801234567"),
    ],
)
def test_split_username(username: str, prefix: str | None, phone: str | None) -> None:
    assert sas_row.split_username(username) == (prefix, phone)


@pytest.mark.parametrize(
    ("prefix", "code"),
    [("KZF06", "KZF06"), ("RBD-01S", "RBD01S"), ("SMR-01", "SMR01"), ("al m-03", "ALM03")],
)
def test_tower_code_from_prefix(prefix: str, code: str) -> None:
    assert sas_row.tower_code_from_prefix(prefix) == code


def test_username_key_is_upper_case_with_latin_digits() -> None:
    assert sas_row.username_key("  alm03-٠٧٨٠١٢٣٤٥٦٧ ") == "ALM03-07801234567"
    assert sas_row.username_key("   ") is None
    assert sas_row.username_key(None) is None


def test_resolve_tower_rule_then_mapping_then_unmapped() -> None:
    towers = {"ALM03": 1, "RBD01S": 2}
    mappings = {"OLD-1": 3, "GONE": None}
    assert sas_row.resolve_tower("RBD-01S", towers, mappings) == (2, "rule")
    assert sas_row.resolve_tower("OLD-1", towers, mappings) == (3, "mapping")
    assert sas_row.resolve_tower("GONE", towers, mappings) == (None, "mapping")
    assert sas_row.resolve_tower("ZZQ07", towers, mappings) == (None, "unmapped")
    assert sas_row.resolve_tower(None, towers, mappings) == (None, "none")
    # The rule wins over a saved mapping of the same prefix.
    assert sas_row.resolve_tower("ALM03", towers, {"ALM03": 3}) == (1, "rule")


# --- dates (R6) ---------------------------------------------------------------------------------


def test_dates_are_baghdad_time_stored_in_utc() -> None:
    assert sas_row.parse_sas_date("2026-12-01 03:00:00") == (
        datetime(2026, 12, 1, 0, 0, tzinfo=UTC),
        False,
    )
    assert sas_row.parse_sas_date("2026/12/01") == (
        datetime(2026, 11, 30, 21, 0, tzinfo=UTC),
        False,
    )
    assert sas_row.parse_sas_date(datetime(2026, 12, 1, 3, 0)) == (
        datetime(2026, 12, 1, 0, 0, tzinfo=UTC),
        False,
    )


@pytest.mark.parametrize("never", [None, "", "0000-00-00 00:00:00", "0000-00-00"])
def test_empty_or_never_dates_are_none_without_the_mark(never) -> None:
    assert sas_row.parse_sas_date(never) == (None, False)


@pytest.mark.parametrize("garbage", ["قريباً", "2026-13-40", "12"])
def test_unreadable_dates_are_none_with_the_mark(garbage: str) -> None:
    assert sas_row.parse_sas_date(garbage) == (None, True)


# --- one row ------------------------------------------------------------------------------------


def _raw(**values) -> dict:
    base = {
        "sas_id": "101",
        "username": "ALM03-07801234567",
        "first_name": " علي  تجريبي ",
        "last_name": "حسن",
        "phone": "+964 780 123 4567",
        "expiration": "2026-12-01 00:00:00",
        "notes": None,
        "parent_name": "admin",
        "created_at": "2025-01-10 10:00:00",
        "last_online": None,
        "group_name": "PLUS",
    }
    return base | values


def test_clean_row_values() -> None:
    row = sas_row.clean_row(2, _raw())
    assert row["index"] == 2
    assert row["username"] == "ALM03-07801234567"
    assert row["username_key"] == "ALM03-07801234567"
    assert row["first_name"] == "علي تجريبي"
    assert row["full_name"] == "علي تجريبي حسن"
    assert row["phone"] == "07801234567"
    assert row["phone_file"] == "+964 780 123 4567"
    assert row["username_phone"] == "07801234567"
    assert row["prefix"] == "ALM03"
    assert row["expires_at"] == "2026-11-30T21:00:00+00:00"
    assert row["last_online_at"] is None
    assert row["base_flags"] == []
    assert row["info"] == []
    assert "password" not in " ".join(row)


def test_clean_row_flags_and_info() -> None:
    assert sas_row.clean_row(3, _raw(username=" "))["base_flags"] == [{"code": "username_missing"}]
    no_phone = sas_row.clean_row(4, _raw(phone="12", username="abc"))
    assert no_phone["phone"] is None
    assert no_phone["phone_file"] == "12"
    assert {"no_valid_phone", "username_no_phone"} <= set(no_phone["info"])
    only_username = sas_row.clean_row(5, _raw(phone=None))
    assert "no_valid_phone" not in only_username["info"]
    assert sas_row.clean_row(6, _raw(expiration="قريباً"))["info"] == ["date_unreadable"]
    nameless = sas_row.clean_row(7, _raw(first_name=None, last_name=None))
    assert nameless["full_name"] == ""


# --- diff (R7) ----------------------------------------------------------------------------------


def _stored(row: dict, **changes) -> dict:
    return {field: row.get(field) for field in sas_row.COMPARED_FIELDS} | {"id": 9} | changes


def test_diff_new_unchanged_update() -> None:
    row = sas_row.clean_row(2, _raw()) | {"tower_id": 1}
    assert sas_row.diff(None, row) == ("new", [])
    assert sas_row.diff(_stored(row), row) == ("unchanged", [])
    kind, changed = sas_row.diff(_stored(row, phone="07709999999", group_name="LITE"), row)
    assert kind == "update"
    assert changed == ["phone", "group_name"]


# --- flags across rows (R9) ---------------------------------------------------------------------


def _rows(*raws) -> list[dict]:
    return [sas_row.clean_row(i + 2, raw) | {"tower_id": None} for i, raw in enumerate(raws)]


def _codes(row: dict) -> list[str]:
    return [flag["code"] for flag in row["flags"]]


def test_repeated_username_in_the_file() -> None:
    rows = sas_row.compute_flags(
        _rows(_raw(), _raw(username="alm03-07801234567", phone="07801111111")), Existing()
    )
    assert rows[0]["flags"] == [{"code": "username_dup_file", "rows": [3]}]
    assert rows[1]["flags"] == [{"code": "username_dup_file", "rows": [2]}]
    assert rows[0]["allowed"] == ["import", "skip"]


def test_username_missing_is_skip_only() -> None:
    (row,) = sas_row.compute_flags(_rows(_raw(username="")), Existing())
    assert _codes(row) == ["username_missing"]
    assert row["allowed"] == ["skip"]


def test_phone_in_sijil_with_another_username() -> None:
    existing = Existing(
        sijil_phones={"07801234567": [("T3C-1004", "SMR01-07801234567")]},
    )
    (row,) = sas_row.compute_flags(_rows(_raw()), existing)
    assert row["flags"] == [{"code": "phone_in_sijil", "requests": ["T3C-1004"]}]
    assert row["allowed"] == ["import", "skip"]


def test_same_username_in_sijil_is_information_only() -> None:
    existing = Existing(
        sijil_phones={"07801234567": [("T3C-1004", "ALM03-07801234567")]},
        sijil_usernames=frozenset({"ALM03-07801234567"}),
    )
    (row,) = sas_row.compute_flags(_rows(_raw()), existing)
    assert row["flags"] == []
    assert row["allowed"] == []
    assert "same_username_in_sijil" in row["info"]


def test_phone_in_sijil_only_for_new_rows_or_changed_phones() -> None:
    sijil = {"07801234567": [("T3C-1004", "SMR01-07801234567")]}
    row = _rows(_raw())[0]
    unchanged = Existing(stored={row["username_key"]: _stored(row)}, sijil_phones=sijil)
    (same,) = sas_row.compute_flags([row], unchanged)
    assert same["kind"] == "unchanged"
    assert same["flags"] == []
    other_group = Existing(
        stored={row["username_key"]: _stored(row, group_name="LITE")}, sijil_phones=sijil
    )
    (group_only,) = sas_row.compute_flags([row], other_group)
    assert group_only["kind"] == "update"
    assert group_only["flags"] == []
    new_phone = Existing(
        stored={row["username_key"]: _stored(row, phone="07709999999")}, sijil_phones=sijil
    )
    (phone_changed,) = sas_row.compute_flags([row], new_phone)
    assert _codes(phone_changed) == ["phone_in_sijil"]
    assert phone_changed["stored_id"] == 9


def test_information_codes_across_rows_and_legacy() -> None:
    rows = sas_row.compute_flags(
        _rows(
            _raw(),
            _raw(username="KZF06-07709999999", phone="07801234567"),
        ),
        Existing(legacy_phones=frozenset({"07709999999"})),
    )
    assert "phone_dup_file" in rows[0]["info"]
    assert "phone_dup_file" in rows[1]["info"]
    assert "phone_in_legacy" in rows[1]["info"]
    assert rows[0]["flags"] == rows[1]["flags"] == []


def test_compute_flags_keeps_choices_and_does_not_mutate() -> None:
    rows = _rows(_raw(), _raw())
    rows[0]["choice"] = "import"
    before = [dict(r) for r in rows]
    flagged = sas_row.compute_flags(rows, Existing())
    assert flagged[0]["choice"] == "import"
    assert rows == before


# --- the synthetic fixture (tasks T011) ---------------------------------------------------------


def test_fixture_gives_the_expected_flags_and_never_a_password() -> None:
    from tests.helpers import sas

    header, *body = sas.fixture_rows("sas_sample.csv")
    columns = sas_row.match_headers(header)
    rows = [
        sas_row.clean_row(i + 2, {key: cells[c] for key, c in columns.items()}) | {"tower_id": None}
        for i, cells in enumerate(body)
    ]
    existing = Existing(
        sijil_phones={
            "07810000014": [("T3C-1001", None)],
            "07810000015": [("T3C-1002", "ALM03-07810000015")],
        },
        sijil_usernames=frozenset({"ALM03-07810000015"}),
    )
    flagged = {
        str(row["index"]): [
            f if f["code"] != "phone_in_sijil" else f | {"requests": ["<pending>"]}
            for f in row["flags"]
        ]
        for row in sas_row.compute_flags(rows, existing)
        if row["flags"]
    }
    expected = sas.expected()
    assert flagged == expected["flagged"]
    assert "07810000022" not in str(rows)  # the second file only
    text = str(rows)
    assert not [p for p in expected["passwords"] if p in text]
    prefixes = [row["prefix"] for row in rows]
    assert prefixes.count("ZZQ07") == 2
    for index, code in expected["towers"].items():
        prefix = rows[int(index) - 2]["prefix"]
        assert (sas_row.tower_code_from_prefix(prefix) if prefix else None) == code
