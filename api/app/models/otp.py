"""Phone OTP challenges (specs/007-phone-otp/data-model.md › otp_challenges). Mirrors 0009.

One row per successful send. State (active, verified, cancelled, expired) is derived, never
stored. `code_hash` is a keyed HMAC (research R3); the plain code is never stored.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utc_now
from app.models.base import Base


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    __table_args__ = (
        CheckConstraint("phone ~ '^07[0-9]{9}$'", name="otp_challenges_phone_format"),
        CheckConstraint("attempts BETWEEN 0 AND 3", name="otp_challenges_attempts_range"),
        Index("otp_challenges_request_created_idx", "request_id", text("created_at DESC")),
        Index("otp_challenges_phone_created_idx", "phone", text("created_at DESC")),
    )

    # Made by the app before hashing: the id is part of the hashed message (research R3).
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    # The draft. Null once the draft is deleted or submitted (008 copies it into `requests` and
    # removes it, specs/008 research R1); the row stays so the hourly limit still counts it.
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id", ondelete="SET NULL")
    )
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()")
    )
