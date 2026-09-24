"""Shift model — the unit of staffing (project blueprint, Section 7 & 10)."""
import enum
import uuid
from datetime import date as date_type
from datetime import datetime
from datetime import time as time_type

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Time, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShiftStatus(str, enum.Enum):
    OPEN = "open"
    PENDING_ACCEPTANCE = "pending_acceptance"
    CONFIRMED = "confirmed"
    UNFILLED = "unfilled"
    CANCELLED = "cancelled"


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        CheckConstraint("min_staff <= max_staff", name="ck_shifts_min_le_max_staff"),
        CheckConstraint("start_time < end_time", name="ck_shifts_start_before_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time_type] = mapped_column(Time, nullable=False)
    end_time: Mapped[time_type] = mapped_column(Time, nullable=False)
    min_staff: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_staff: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[ShiftStatus] = mapped_column(
        SAEnum(
            ShiftStatus,
            name="shift_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ShiftStatus.OPEN,
    )
    # Answers "has this shift ever satisfied the roster rule" — separate
    # from `status`, which is allowed to move between pending_acceptance and
    # confirmed as top-up offers come and go. GET /roster reads this field,
    # not `status`. See recompute_shift_status() and the project blueprint,
    # Section 10.
    roster_locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
