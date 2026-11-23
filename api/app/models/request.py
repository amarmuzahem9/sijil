"""Submitted requests (specs/008-submission-decision/data-model.md). Mirrors migration 0010.

A request is a draft after submission: every value is copied and fixed (Principle IV), and the
draft row is removed. Requests are never deleted (Principle III): there is no delete path.
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
        CheckConstraint("NOT no_surname OR surname IS NULL", name="requests_no_surname"),
        CheckConstraint("no_surname OR surname IS NOT NULL", name="requests_surname_required"),
        CheckConstraint("national_id ~ '^[0-9]{12}$'", name="requests_national_id_format"),
        CheckConstraint("family_key ~ '^[A-Z0-9]+$'", name="requests_family_key_format"),
        CheckConstraint("phone ~ '^07[0-9]{9}$'", name="requests_phone_format"),
        CheckConstraint(
            "status <> 'approved' OR approved_at IS NOT NULL", name="requests_approved_has_time"
        ),
        CheckConstraint(
            "status <> 'pending_review' OR approved_at IS NULL", name="requests_pending_no_time"
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

    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    father_name: Mapped[str] = mapped_column(Text, nullable=False)
    grandfather_name: Mapped[str] = mapped_column(Text, nullable=False)
    great_grandfather_name: Mapped[str] = mapped_column(Text, nullable=False)
    surname: Mapped[str | None] = mapped_column(Text)
    mother_first_name: Mapped[str] = mapped_column(Text, nullable=False)
    mother_second_name: Mapped[str] = mapped_column(Text, nullable=False)
    mother_third_name: Mapped[str | None] = mapped_column(Text)
    mother_surname: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    no_surname: Mapped[bool] = mapped_column(Boolean, nullable=False)
    national_id: Mapped[str] = mapped_column(Text, nullable=False)
    national_id_input: Mapped[str] = mapped_column(Text, nullable=False)
    family_number: Mapped[str] = mapped_column(Text, nullable=False)
    family_key: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_place: Mapped[str] = mapped_column(Text, nullable=False)
    issuing_authority: Mapped[str] = mapped_column(Text, nullable=False)
    card_fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    national_id_check: Mapped[dict | None] = mapped_column(JSONB)
    # Raw and ruled readings per side. Never returned to a page or logged (Principle II).
    card_readings: Mapped[dict] = mapped_column(JSONB, nullable=False)

    location_lat: Mapped[float] = mapped_column(Float, nullable=False)
    location_lng: Mapped[float] = mapped_column(Float, nullable=False)
    location_source: Mapped[str] = mapped_column(Text, nullable=False)
    location_accuracy_m: Mapped[int | None] = mapped_column(Integer)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    landmark: Mapped[str] = mapped_column(Text, nullable=False)

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

    phone: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    otp_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Null with approved_at set = the automatic approval of §6.1 row 5.
    approved_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()

    reasons: Mapped[list["RequestReason"]] = relationship(
        back_populates="request", lazy="selectin", order_by="RequestReason.id"
    )
    images: Mapped[list["RequestImage"]] = relationship(back_populates="request", lazy="selectin")
    # «المسوّق» in «نسخ التفاصيل» (system.md v1.11 §5.5). `approved_by` also points at users.
    marketer: Mapped["User"] = relationship(foreign_keys=[marketer_id], lazy="joined")  # noqa: F821

    @property
    def number_label(self) -> str:
        return f"T3C-{self.number}"


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
