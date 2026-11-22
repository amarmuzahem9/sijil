"""Drafts of new-subscriber requests (specs/005-subscriber-form/data-model.md).

A draft is not a request (docs/system.md §5 v1.4): every field may be empty or invalid, it has no
request number, and its owner may delete it. Mirrors migration 0005.
"""

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utc_now
from app.models.base import Base

# data-model.md › drafts / draft_images — limits shared by the service and the validation.
TEXT_LIMITS: dict[str, int] = {
    "subscriber_name": 100,
    "national_id": 30,
    "family_number": 30,
    "address": 300,
    "landmark": 200,
    "phone_input": 30,
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
        Index("drafts_marketer_updated_idx", "marketer_id", text("updated_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    marketer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="draft", server_default=text("'draft'")
    )

    subscriber_name: Mapped[str | None] = mapped_column(Text)
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

    phone_input: Mapped[str | None] = mapped_column(Text)
    phone_normalized: Mapped[str | None] = mapped_column(Text)

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
