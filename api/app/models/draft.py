"""Drafts of new-subscriber requests (specs/005-subscriber-form/data-model.md).

A draft is not a request (docs/system.md §5 v1.4): every field may be empty or invalid, it has no
request number, and its owner may delete it. Mirrors migration 0005.
"""

import uuid
from datetime import date, datetime
from typing import Literal

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

# The nine name fields of the ministry form, in page order (system.md §5.1 v1.5).
NAME_FIELDS: tuple[str, ...] = (
    "first_name",
    "father_name",
    "grandfather_name",
    "great_grandfather_name",
    "surname",
    "mother_first_name",
    "mother_second_name",
    "mother_third_name",
    "mother_surname",
)
# `full_name` = these five, joined by one space, empty parts skipped (research.md R12).
FULL_NAME_FIELDS: tuple[str, ...] = NAME_FIELDS[:5]
OPTIONAL_NAME_FIELDS: tuple[str, ...] = ("mother_third_name", "mother_surname")
NAME_MAX = 50

# The eight form fields the card reading may fill (specs/006 data-model.md › drafts.card_fields).
CARD_FIELDS: tuple[str, ...] = (
    "first_name",
    "father_name",
    "grandfather_name",
    "surname",
    "mother_first_name",
    "mother_second_name",
    "national_id",
    "family_number",
    # The other fields on the back (owner change, system.md v1.8, research R13).
    "birth_date",
    "birth_place",
    "issue_date",
    "expiry_date",
    "issuing_authority",
)
BACK_TEXT_MAX = 100

# data-model.md › drafts / draft_images — limits shared by the service and the validation.
TEXT_LIMITS: dict[str, int] = {
    **{name: NAME_MAX for name in NAME_FIELDS},
    "national_id": 30,
    "family_number": 30,
    "address": 300,
    "landmark": 200,
    "phone_input": 30,
    # Back of the card (owner change, system.md v1.8).
    "birth_place": 100,
    "issuing_authority": 100,
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_EDGE = 1600

Side = Literal["front", "back"]
SIDES: tuple[Side, ...] = ("front", "back")
LOCATION_SOURCES = ("gps", "map")


def _ts() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()")
    )


class Draft(Base):
    __tablename__ = "drafts"
    __table_args__ = (
        CheckConstraint("status = 'draft'", name="drafts_status_draft"),
        CheckConstraint(
            "(location_lat IS NULL) = (location_lng IS NULL)", name="drafts_location_pair"
        ),
        CheckConstraint(
            "(otp_verified_at IS NULL) = (otp_context_hash IS NULL)", name="drafts_otp_pair"
        ),
        Index("drafts_marketer_updated_idx", "marketer_id", text("updated_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    marketer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="draft", server_default=text("'draft'")
    )

    first_name: Mapped[str | None] = mapped_column(Text)
    father_name: Mapped[str | None] = mapped_column(Text)
    grandfather_name: Mapped[str | None] = mapped_column(Text)
    great_grandfather_name: Mapped[str | None] = mapped_column(Text)
    surname: Mapped[str | None] = mapped_column(Text)
    mother_first_name: Mapped[str | None] = mapped_column(Text)
    mother_second_name: Mapped[str | None] = mapped_column(Text)
    mother_third_name: Mapped[str | None] = mapped_column(Text)
    mother_surname: Mapped[str | None] = mapped_column(Text)
    # Computed by draft_service on every save; never accepted from the client.
    full_name: Mapped[str | None] = mapped_column(Text)
    national_id: Mapped[str | None] = mapped_column(Text)
    family_number: Mapped[str | None] = mapped_column(Text)

    location_lat: Mapped[float | None] = mapped_column(Float)
    location_lng: Mapped[float | None] = mapped_column(Float)
    location_source: Mapped[str | None] = mapped_column(Text)
    location_accuracy_m: Mapped[int | None] = mapped_column(Integer)
    address: Mapped[str | None] = mapped_column(Text)
    landmark: Mapped[str | None] = mapped_column(Text)

    area_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("areas.id", ondelete="SET NULL")
    )
    tower_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("towers.id", ondelete="SET NULL")
    )
    plan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("plans.id", ondelete="SET NULL")
    )
    # Copies taken from the catalog at every save; final at submission (research.md R4).
    area_name: Mapped[str | None] = mapped_column(Text)
    tower_code: Mapped[str | None] = mapped_column(Text)
    plan_name: Mapped[str | None] = mapped_column(Text)
    trial_price: Mapped[int | None] = mapped_column(Integer)
    second_price: Mapped[int | None] = mapped_column(Integer)

    # Feature 006 (data-model.md): provenance of the card fields, «لا يوجد لقب على البطاقة», and
    # the national-ID check against a verified MRZ ({mrz, confirmed_value} or null).
    card_fields: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    no_surname: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    national_id_check: Mapped[dict | None] = mapped_column(JSONB)
    # Back of the card (migration 0008): required only for sending (system.md v1.8).
    birth_date: Mapped[date | None] = mapped_column(Date)
    birth_place: Mapped[str | None] = mapped_column(Text)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    issuing_authority: Mapped[str | None] = mapped_column(Text)

    phone_input: Mapped[str | None] = mapped_column(Text)
    phone_normalized: Mapped[str | None] = mapped_column(Text)
    # Feature 007 (data-model.md): set by a successful OTP verify; both cleared by any save that
    # changes the phone, tower, category or prices (research R5). 008 rechecks the hash.
    otp_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    otp_context_hash: Mapped[str | None] = mapped_column(Text)
    # Feature 008 (data-model.md): the family key confirmed with «طلب اشتراك إضافي». Valid only
    # while it equals family_key(family_number) and a family match exists (research R12).
    additional_confirmed_key: Mapped[str | None] = mapped_column(Text)

    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    # X-Client-Id of the page load that made the last change (research.md R3).
    last_client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()

    # Optimistic concurrency (research.md R3): every UPDATE is `... WHERE version = :loaded`
    # and increments it; zero rows matched raises StaleDataError, mapped to 409 draft_conflict.
    __mapper_args__ = {"version_id_col": version}

    images: Mapped[list["DraftImage"]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    card_readings: Mapped[list["CardReading"]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class DraftImage(Base):
    __tablename__ = "draft_images"
    __table_args__ = (
        UniqueConstraint("draft_id", "side", name="draft_images_draft_side_key"),
        CheckConstraint("side IN ('front', 'back')", name="draft_images_side"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id", ondelete="CASCADE"), nullable=False
    )
    side: Mapped[str] = mapped_column(Text, nullable=False)
    # `<uuid4 hex>.jpg` inside UPLOADS_DIR; never a user-supplied name.
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _ts()

    draft: Mapped[Draft] = relationship(back_populates="images")


class ImageAccessLog(Base):
    """Append-only: one row per successful image open (§13, Principle II)."""

    __tablename__ = "image_access_log"
    __table_args__ = (Index("image_access_log_created_at_idx", text("created_at DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # Plain values, not FKs: the history outlives draft deletion (research.md R8).
    image_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    side: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _ts()
    # `view` = a person opened the image (005); `ocr` = the server sent it to the card reader
    # (specs/006 data-model.md, analysis C1).
    purpose: Mapped[str] = mapped_column(
        Text, nullable=False, default="view", server_default=text("'view'")
    )


class CardReading(Base):
    """The latest reading of one side of a draft's card (specs/006 data-model.md › card_readings).

    `raw` is the reader's answer as received; `result` is the side after the rules (R6). Neither
    is ever sent to the page (research R11) or logged.
    """

    __tablename__ = "card_readings"
    __table_args__ = (
        UniqueConstraint("draft_id", "side", name="card_readings_draft_side_key"),
        CheckConstraint("side IN ('front', 'back')", name="card_readings_side"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id", ondelete="CASCADE"), nullable=False
    )
    side: Mapped[str] = mapped_column(Text, nullable=False)
    image_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default=text("'pending'")
    )
    reason: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict | None] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    queued_by_client: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()

    draft: Mapped[Draft] = relationship(back_populates="card_readings")
