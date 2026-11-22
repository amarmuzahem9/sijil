"""sessions — data-model.md › sessions. One row per signed-in device (refresh-token family)."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import utc_now
from app.models.base import Base

REVOKE_REASONS = (
    "logout",
    "password_changed",
    "password_reset",
    "deactivated",
    "reuse_detected",
    "archived",
)
USER_AGENT_MAX = 255


class UserSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "revoke_reason IS NULL OR revoke_reason IN "
            "('logout', 'password_changed', 'password_reset', 'deactivated', 'reuse_detected', "
            "'archived')",
            name="sessions_revoke_reason_valid",
        ),
        CheckConstraint(
            "user_agent IS NULL OR char_length(user_agent) <= 255",
            name="sessions_user_agent_length",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    previous_token_hash: Mapped[str | None] = mapped_column(Text, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)

    def is_valid(self, now: datetime) -> bool:
        return self.revoked_at is None and now < self.expires_at
