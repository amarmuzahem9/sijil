"""SAS import test helpers (specs/015). Synthetic values only: made-up usernames, names, phones and
`SYNTH-PW-<n>` markers in the `ct_password` column (they must never be found in Sijil, SC-003)."""

import csv
import io
import json
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Area, Tower

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sas"
TOWER_CODES = ("ALM03", "KZF06", "RBD01S", "SMR01")


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def fixture_rows(name: str) -> list[list[str]]:
    """Header row first, as in the file."""
    text = fixture_bytes(name).decode("utf-8")
    return [list(row) for row in csv.reader(io.StringIO(text, newline=""))]


def expected() -> dict[str, Any]:
    return json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


def passwords() -> list[str]:
    return expected()["passwords"]


def to_xlsx(rows: list[list[Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()


def to_csv(rows: list[list[Any]]) -> bytes:
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue().encode("utf-8")


def seed_towers(db: Session, codes: tuple[str, ...] = TOWER_CODES) -> dict[str, int]:
    """The towers the fixture usernames resolve to by the rule; existing ones are reused."""
    found = {t.code: t.id for t in db.scalars(select(Tower).where(Tower.code.in_(codes)))}
    missing = [code for code in codes if code not in found]
    if missing:
        area = db.scalar(select(Area).where(Area.name == "منطقة SAS تجريبية"))
        if area is None:
            area = Area(name="منطقة SAS تجريبية")
            db.add(area)
            db.flush()
        for code in missing:
            tower = Tower(code=code, name=f"برج {code}", area_id=area.id)
            db.add(tower)
            db.flush()
            found[code] = tower.id
    return found
