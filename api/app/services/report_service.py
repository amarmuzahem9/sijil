"""The requests report of «التقارير والتصدير» (docs/system.md v1.25 §11; specs/019 research R2–R4,
R12, R13).

One filter over `requests` (drafts live in another table, so they never appear) serves the page,
the summaries and, later, the export. Only the listed columns are selected: no identity, contact,
address or money column, whoever asks (FR-002, FR-016). A deleted request matches by its kept
fields and is shown without a name (§7.4).
"""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.core.access import has_any_permission
from app.core.report_period import period_bounds
from app.core.timeutil import baghdad_today
from app.models import Area, Plan, Request, Tower, User
from app.schemas.reports import ReportFilters
from app.services.review_service import can_review

PAGE_SIZE = 50


def can_export_identity(user: User) -> bool:
    """The main admin, or `reports` together with `review` (owner Q1; research R1)."""
    return has_any_permission(user.role, user.permissions, ["reports"]) and can_review(user)


def date_column(filters: ReportFilters):
    return Request.submitted_at if filters.date_kind == "submitted" else Request.linked_at


def conditions(filters: ReportFilters, today: date | None = None) -> list[ColumnElement[bool]]:
    """The WHERE of the report and the export. Raises PeriodError for a bad period."""
    start, end = period_bounds(
        filters.period, today=today or baghdad_today(), from_=filters.from_, to=filters.to
    )
    column = date_column(filters)
    out: list[ColumnElement[bool]] = [column >= start, column < end]
    if filters.date_kind == "linked":
        # The current link only (013): an undone link has no link date.
        out.append(Request.status == "linked")
    for value, col in (
        (filters.area_id, Request.area_id),
        (filters.tower_id, Request.tower_id),
        (filters.marketer_id, Request.marketer_id),
        (filters.plan_id, Request.plan_id),
        (filters.status, Request.status),
        (filters.type, Request.type),
    ):
        if value is not None:
            out.append(col == value)
    return out


@dataclass(frozen=True)
class Row:
    id: int
    number: int
    number_label: str
    name: str | None
    deleted: bool
    tower: str
    plan: str
    marketer: str
    status: str
    type: str
    submitted_at: datetime
    linked_at: datetime | None


def tower_label(name: str, code: str) -> str:
    return f"{name} ({code})"


def _rows_select(where: list[ColumnElement[bool]], filters: ReportFilters) -> Select:
    column = date_column(filters)
    return (
        select(
            Request.id,
            Request.number,
            Request.full_name,
            Request.deleted_at,
            Request.tower_name,
            Request.tower_code,
            Request.plan_name,
            User.name.label("marketer_name"),
            Request.status,
            Request.type,
            Request.submitted_at,
            Request.linked_at,
        )
        .join(User, User.id == Request.marketer_id)
        .where(*where)
        .order_by(column.desc(), Request.id.desc())
    )


def _row(r) -> Row:
    deleted = r.deleted_at is not None
    return Row(
        id=r.id,
        number=r.number,
        number_label=f"T3C-{r.number}",
        name=None if deleted else r.full_name,
        deleted=deleted,
        tower=tower_label(r.tower_name, r.tower_code),
        plan=r.plan_name,
        marketer=r.marketer_name,
        status=r.status,
        type=r.type,
        submitted_at=r.submitted_at,
        linked_at=r.linked_at,
    )


def count(db: Session, where: list[ColumnElement[bool]]) -> int:
    return db.scalar(select(func.count()).select_from(Request).where(*where)) or 0


def page(
    db: Session, filters: ReportFilters, where: list[ColumnElement[bool]], number: int
) -> list[Row]:
    query = _rows_select(where, filters).offset((number - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    return [_row(r) for r in db.execute(query)]


def all_rows(db: Session, filters: ReportFilters, where: list[ColumnElement[bool]]) -> list[Row]:
    """Every matching row in report order (the export, capped by its caller)."""
    return [_row(r) for r in db.execute(_rows_select(where, filters))]


@dataclass(frozen=True)
class Summary:
    by_status: list[dict]
    by_tower: list[dict]
    by_marketer: list[dict]


def summaries(db: Session, where: list[ColumnElement[bool]]) -> Summary:
    n = func.count().label("n")
    by_status = db.execute(
        select(Request.status, n).where(*where).group_by(Request.status).order_by(n.desc())
    ).all()
    # One line per tower, named as the catalog names it now; the rows keep the stored names.
    by_tower = db.execute(
        select(Request.tower_id, Tower.name, Tower.code, n)
        .join(Tower, Tower.id == Request.tower_id)
        .where(*where)
        .group_by(Request.tower_id, Tower.name, Tower.code)
        .order_by(n.desc(), Tower.code)
    ).all()
    by_marketer = db.execute(
        select(Request.marketer_id, User.name, n)
        .join(User, User.id == Request.marketer_id)
        .where(*where)
        .group_by(Request.marketer_id, User.name)
        .order_by(n.desc(), User.name)
    ).all()
    return Summary(
        by_status=[{"status": s, "count": c} for s, c in by_status],
        by_tower=[
            {"tower_id": t, "tower": tower_label(name, code), "count": c}
            for t, name, code, c in by_tower
        ],
        by_marketer=[
            {"marketer_id": m, "marketer": name, "count": c} for m, name, c in by_marketer
        ],
    )


def options(db: Session) -> dict:
    """Every area, tower, plan and marketer, active or not, archived marketers included (R13)."""
    areas = db.scalars(select(Area).order_by(Area.name)).all()
    towers = db.scalars(select(Tower).order_by(Tower.code)).all()
    plans = db.scalars(select(Plan).order_by(Plan.name)).all()
    marketers = db.scalars(select(User).where(User.role == "marketer").order_by(User.name)).all()
    return {
        "areas": [{"id": a.id, "name": a.name, "active": a.is_active} for a in areas],
        "towers": [
            {
                "id": t.id,
                "code": t.code,
                "name": t.name,
                "area_id": t.area_id,
                "active": t.is_active,
            }
            for t in towers
        ],
        "plans": [{"id": p.id, "name": p.name, "active": p.is_active} for p in plans],
        "marketers": [
            {
                "id": m.id,
                "name": m.name,
                "archived": m.archived_at is not None,
                "active": m.is_active,
            }
            for m in marketers
        ],
    }
