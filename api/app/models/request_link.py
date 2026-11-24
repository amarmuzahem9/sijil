"""Every «تم الربط» and every undo of one request (specs/013 data-model.md › `request_links`).

Mirrors migration 0016. Append-only: rows are never updated or deleted (constitution Principle
III). The current link of a linked request is its newest `linked` row; its id is the `link_id`
the undo must send back.
"""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

LINK_KINDS = ("linked", "unlinked")


class RequestLink(Base):
    __tablename__ = "request_links"
    __table_args__ = (
        CheckConstraint("kind IN ('linked','unlinked')", name="request_links_kind"),
        CheckConstraint(
            "CASE WHEN kind = 'linked' THEN reason IS NULL "
            "ELSE reason IS NOT NULL AND reason IN "
            "('not_linked_in_sas','by_mistake','other_request_linked','other') END",
            name="request_links_reason",
        ),
        Index("request_links_request", "request_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("requests.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
