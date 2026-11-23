"""Submitted requests (specs/008-submission-decision/data-model.md). Mirrors migration 0010.

A request is a draft after submission: every value is copied and fixed (Principle IV), and the
draft row is removed. Requests are never deleted (Principle III). A pending or rejected request
may be erased in place (constitution III v1.3.0, specs/011): its personal columns become NULL and
the row keeps a deletion mark. The personal columns are therefore nullable; `requests_erasure`
keeps them required on every live row.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utc_now
from app.models.base import Base

REQUEST_TYPES = ("new", "additional", "return")
REQUEST_STATUSES = ("pending_review", "approved", "rejected", "linked")
# Statuses that make a request an "existing subscriber" for the checks (system.md §6.1 v1.9).
ACTIVE_STATUSES = ("pending_review", "approved", "linked")
REASONS = ("family_exists", "numbers_edited", "return", "numbers_conflict")
# specs/010 data-model.md › request_reasons.state
REASON_STATES = ("open", "resolved", "not_applicable")
# specs/010 research R6; labels in app/core/rejection_reasons.py
REJECTION_REASONS = (
    "card_unclear",
    "numbers_mismatch",
    "under_15_days",
    "active_subscription",
    "other",
)
PIN_FIELDS = ("national_id", "family_number")
PIN_SOURCES = ("reading", "mrz", "marketer", "typed")
# specs/011 data-model.md › Deletion reasons; labels in app/core/deletion_reasons.py
DELETION_REASONS = ("duplicate", "test", "entry_error", "other")
DELETABLE_STATUSES = ("pending_review", "rejected")
# specs/011 data-model.md › requests: required on a live row, NULL on a deleted one.
MADE_NULLABLE = (
    "first_name",
    "father_name",
    "grandfather_name",
    "great_grandfather_name",
    "full_name",
    "mother_first_name",
    "mother_second_name",
    "no_surname",
    "national_id",
    "national_id_input",
    "submitted_national_id",
    "family_number",
    "submitted_family_number",
    "family_key",
    "birth_date",
    "issue_date",
    "expiry_date",
    "birth_place",
    "issuing_authority",
    "card_fields",
    "card_readings",
    "location_lat",
    "location_lng",
    "location_source",
    "address",
    "landmark",
    "phone",
    "username",
)
# Every column a deletion sets to NULL.
ERASED_COLUMNS = MADE_NULLABLE + (
    "surname",
    "mother_third_name",
    "mother_surname",
    "national_id_check",
    "location_accuracy_m",
    "rejection_note",
)
_LIVE = " AND ".join(f"{c} IS NOT NULL" for c in MADE_NULLABLE)
_ERASED = " AND ".join(f"{c} IS NULL" for c in ERASED_COLUMNS)


def _ts() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()")
    )


class Request(Base):
    __tablename__ = "requests"
    __table_args__ = (
        UniqueConstraint("number", name="requests_number_key"),
        UniqueConstraint("draft_id", name="requests_draft_id_key"),
        CheckConstraint("type IN ('new','additional','return')", name="requests_type"),
        CheckConstraint(
            "status IN ('pending_review','approved','rejected','linked')", name="requests_status"
        ),
        CheckConstraint(
            "deleted_at IS NOT NULL OR (NOT no_surname OR surname IS NULL)",
            name="requests_no_surname",
        ),
        CheckConstraint(
            "deleted_at IS NOT NULL OR (no_surname OR surname IS NOT NULL)",
            name="requests_surname_required",
        ),
        CheckConstraint("national_id ~ '^[0-9]{12}$'", name="requests_national_id_format"),
        CheckConstraint("family_key ~ '^[A-Z0-9]+$'", name="requests_family_key_format"),
        CheckConstraint("phone ~ '^07[0-9]{9}$'", name="requests_phone_format"),
        CheckConstraint(
            "status <> 'approved' OR approved_at IS NOT NULL", name="requests_approved_has_time"
        ),
        CheckConstraint(
            "status <> 'pending_review' OR approved_at IS NULL", name="requests_pending_no_time"
        ),
        # specs/010 data-model.md (migration 0013)
        CheckConstraint(
            "rejection_reason IS NULL OR rejection_reason IN ('card_unclear','numbers_mismatch',"
            "'under_15_days','active_subscription','other')",
            name="requests_rejection_reason",
        ),
        CheckConstraint(
            "(status = 'rejected') = (rejected_at IS NOT NULL AND rejected_by IS NOT NULL "
            "AND rejection_reason IS NOT NULL)",
            name="requests_rejected_has_decision",
        ),
        CheckConstraint(
            "deleted_at IS NOT NULL OR (CASE WHEN rejection_reason = 'other' "
            "THEN rejection_note IS NOT NULL AND btrim(rejection_note) <> '' "
            "ELSE rejection_note IS NULL END)",
            name="requests_rejection_note",
        ),
        CheckConstraint(
            "status <> 'rejected' OR approved_at IS NULL", name="requests_rejected_no_approval"
        ),
        # specs/011 data-model.md (migration 0014)
        CheckConstraint(
            "(deleted_at IS NULL) = (deleted_by IS NULL) "
            "AND (deleted_at IS NULL) = (deletion_reason IS NULL)",
            name="requests_deletion_mark",
        ),
        CheckConstraint(
            "deletion_reason IS NULL OR deletion_reason IN "
            "('duplicate','test','entry_error','other')",
            name="requests_deletion_reason",
        ),
        CheckConstraint(
            "deleted_at IS NULL OR status IN ('pending_review','rejected')",
            name="requests_deletable_status",
        ),
        CheckConstraint(
            f"CASE WHEN deleted_at IS NULL THEN {_LIVE} ELSE {_ERASED} END",
            name="requests_erasure",
        ),
        Index(
            "requests_pending_idx",
            "submitted_at",
            postgresql_where=text("status = 'pending_review' AND deleted_at IS NULL"),
        ),
        Index("requests_phone_idx", "phone"),
        Index("requests_national_id_idx", "national_id"),
        Index("requests_family_key_idx", "family_key"),
        Index("requests_marketer_submitted_idx", "marketer_id", text("submitted_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    marketer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)

    first_name: Mapped[str | None] = mapped_column(Text)
    father_name: Mapped[str | None] = mapped_column(Text)
    grandfather_name: Mapped[str | None] = mapped_column(Text)
    great_grandfather_name: Mapped[str | None] = mapped_column(Text)
    surname: Mapped[str | None] = mapped_column(Text)
    mother_first_name: Mapped[str | None] = mapped_column(Text)
    mother_second_name: Mapped[str | None] = mapped_column(Text)
    mother_third_name: Mapped[str | None] = mapped_column(Text)
    mother_surname: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str | None] = mapped_column(Text)
    no_surname: Mapped[bool | None] = mapped_column(Boolean)
    national_id: Mapped[str | None] = mapped_column(Text)
    national_id_input: Mapped[str | None] = mapped_column(Text)
    family_number: Mapped[str | None] = mapped_column(Text)
    # The marketer's values as submitted; a pin never changes them (specs/010 R4).
    submitted_national_id: Mapped[str | None] = mapped_column(Text)
    submitted_family_number: Mapped[str | None] = mapped_column(Text)
    family_key: Mapped[str | None] = mapped_column(Text)
    birth_date: Mapped[date | None] = mapped_column(Date)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    birth_place: Mapped[str | None] = mapped_column(Text)
    issuing_authority: Mapped[str | None] = mapped_column(Text)
    card_fields: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    national_id_check: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    # Raw and ruled readings per side. Never returned to a page or logged (Principle II).
    # `none_as_null`: a deletion stores SQL NULL, not JSON null (`requests_erasure`, specs/011).
    card_readings: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))

    location_lat: Mapped[float | None] = mapped_column(Float)
    location_lng: Mapped[float | None] = mapped_column(Float)
    location_source: Mapped[str | None] = mapped_column(Text)
    location_accuracy_m: Mapped[int | None] = mapped_column(Integer)
    address: Mapped[str | None] = mapped_column(Text)
    landmark: Mapped[str | None] = mapped_column(Text)

    area_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("areas.id", ondelete="RESTRICT"), nullable=False
    )
    tower_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("towers.id", ondelete="RESTRICT"), nullable=False
    )
    plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    area_name: Mapped[str] = mapped_column(Text, nullable=False)
    tower_code: Mapped[str] = mapped_column(Text, nullable=False)
    tower_name: Mapped[str] = mapped_column(Text, nullable=False)  # system.md v1.12 §5
    plan_name: Mapped[str] = mapped_column(Text, nullable=False)
    trial_price: Mapped[int] = mapped_column(Integer, nullable=False)
    second_price: Mapped[int] = mapped_column(Integer, nullable=False)

    phone: Mapped[str | None] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(Text)
    otp_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Null with approved_at set = the automatic approval of §6.1 row 5.
    approved_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    # The decision (specs/010 data-model.md › requests).
    counts_commission: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    approval_warnings: Mapped[list | None] = mapped_column(JSONB)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    rejection_note: Mapped[str | None] = mapped_column(Text)
    # The deletion mark (specs/011 data-model.md › requests). Set once, never cleared.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    deletion_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()

    reasons: Mapped[list["RequestReason"]] = relationship(
        back_populates="request", lazy="selectin", order_by="RequestReason.id"
    )
    images: Mapped[list["RequestImage"]] = relationship(back_populates="request", lazy="selectin")
    pins: Mapped[list["RequestNumberPin"]] = relationship(
        back_populates="request", lazy="selectin", order_by="RequestNumberPin.id"
    )
    # «المسوّق» in «نسخ التفاصيل» (system.md v1.11 §5.5). `approved_by` also points at users.
    marketer: Mapped["User"] = relationship(foreign_keys=[marketer_id], lazy="joined")  # noqa: F821

    @property
    def number_label(self) -> str:
        return f"T3C-{self.number}"

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class RequestReason(Base):
    __tablename__ = "request_reasons"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('family_exists','numbers_edited','return','numbers_conflict')",
            name="request_reasons_reason",
        ),
        # Created as UNIQUE NULLS NOT DISTINCT by migration 0010.
        UniqueConstraint(
            "request_id",
            "reason",
            "matched_source",
            "matched_ref",
            name="request_reasons_unique",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(
            "state IN ('open','resolved','not_applicable')", name="request_reasons_state"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    matched_source: Mapped[str | None] = mapped_column(Text)
    matched_ref: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = _ts()
    # specs/010 research R3: rows are marked, never deleted.
    state: Mapped[str] = mapped_column(
        Text, nullable=False, default="open", server_default=text("'open'")
    )
    state_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state_changed_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    # Null: recorded at submission. Set: added by the re-check after a pin.
    added_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))

    request: Mapped[Request] = relationship(back_populates="reasons")


class RequestImage(Base):
    __tablename__ = "request_images"
    __table_args__ = (
        UniqueConstraint("request_id", "side", name="request_images_request_side_key"),
        CheckConstraint("side IN ('front','back')", name="request_images_side"),
    )

    # The draft image's id, kept, so image history stays traceable.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("requests.id", ondelete="RESTRICT"), nullable=False
    )
    side: Mapped[str] = mapped_column(Text, nullable=False)
    # The same file in UPLOADS_DIR as the draft image; never moved.
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    request: Mapped[Request] = relationship(back_populates="images")


class RequestNumberPin(Base):
    """One pin of a national ID or family number by a review admin (specs/010 data-model.md >
    request_number_pins). Append-only: there is no update or delete path. It holds the value
    before and after, which the audit entry reaches through `pin_id` (constitution III v1.2.1).
    Its values never go into an audit entry or a log line (Principle II)."""

    __tablename__ = "request_number_pins"
    __table_args__ = (
        CheckConstraint(
            "field IN ('national_id','family_number')", name="request_number_pins_field"
        ),
        CheckConstraint(
            "source IN ('reading','mrz','marketer','typed')", name="request_number_pins_source"
        ),
        CheckConstraint(
            "source <> 'mrz' OR field = 'national_id'", name="request_number_pins_mrz_nid"
        ),
        Index("request_number_pins_request_idx", "request_id", "pinned_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("requests.id", ondelete="RESTRICT"), nullable=False
    )
    field: Mapped[str] = mapped_column(Text, nullable=False)
    previous_value: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    pinned_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    pinned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    request: Mapped[Request] = relationship(back_populates="pins")
