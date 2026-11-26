"""Commission payments (specs/017 data-model.md). Append-only: never updated or deleted
(constitution Principle IV, a paid commission month is locked)."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.catalog import MAX_AMOUNT


class CommissionPayment(Base):
    """One «تم الدفع» of one marketer for one Baghdad month, with the figures it locked."""

    __tablename__ = "commission_payments"
    __table_args__ = (
        UniqueConstraint("marketer_id", "month", name="commission_payments_marketer_month"),
        CheckConstraint("extract(day from month) = 1", name="commission_payments_month_first_day"),
        CheckConstraint("count > 0", name="commission_payments_count"),
        CheckConstraint(
            "tier_min_count >= 0 AND tier_min_count <= count", name="commission_payments_tier"
        ),
        CheckConstraint(f"rate BETWEEN 1 AND {MAX_AMOUNT}", name="commission_payments_rate_range"),
        CheckConstraint("amount = count::bigint * rate", name="commission_payments_amount"),
        Index("commission_payments_month", "month"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    marketer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # The first day of the Baghdad month.
    month: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    tier_min_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paid_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommissionPaymentRequest(Base):
    """A request counted in a payment. Keyed by request: a request is paid at most once."""

    __tablename__ = "commission_payment_requests"
    __table_args__ = (Index("commission_payment_requests_payment", "payment_id"),)

    request_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("requests.id"), primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("commission_payments.id"), nullable=False
    )
