"""Settings tables (specs/004-settings/data-model.md): areas, towers, plans, tiers, app settings.

Every FK pointing at areas/towers/plans is ON DELETE RESTRICT: an item that anything refers to can
never be deleted, only deactivated (docs/system.md §10 v1.3, research.md R2).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.timeutil import utc_now
from app.models.base import Base

MAX_AMOUNT = 10_000_000


def _created() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=text("now()")
    )


def _updated() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("now()"),
    )


class Area(Base):
    __tablename__ = "areas"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 100", name="areas_name_length"),
        Index("areas_name_key", func.lower(text("name")), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Tower(Base):
    __tablename__ = "towers"
    __table_args__ = (
        UniqueConstraint("code", name="towers_code_key"),
        CheckConstraint("code ~ '^[A-Z0-9]{2,20}$'", name="towers_code_format"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 100", name="towers_name_length"),
        Index("towers_area_id_idx", "area_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    area_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("areas.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    area: Mapped[Area] = relationship(lazy="joined")


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 100", name="plans_name_length"),
        CheckConstraint(f"trial_price BETWEEN 0 AND {MAX_AMOUNT}", name="plans_trial_price_range"),
        CheckConstraint(
            f"second_price BETWEEN 0 AND {MAX_AMOUNT}", name="plans_second_price_range"
        ),
        Index("plans_name_key", func.lower(text("name")), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    trial_price: Mapped[int] = mapped_column(Integer, nullable=False)
    second_price: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class RewardTier(Base):
    __tablename__ = "reward_tiers"
    __table_args__ = (
        UniqueConstraint("min_count", name="reward_tiers_min_count_key"),
        CheckConstraint("min_count BETWEEN 0 AND 10000", name="reward_tiers_min_count_range"),
        CheckConstraint(f"rate BETWEEN 1 AND {MAX_AMOUNT}", name="reward_tiers_rate_range"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    min_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rate: Mapped[int] = mapped_column(Integer, nullable=False)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = _updated()
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
