"""Availability model.

Location-agnostic by design (project blueprint, Section 7): an employee's
free time isn't tied to a store, only their eligibility to be offered a
shift there is.
"""
import uuid
from datetime import date as date_type
from datetime import datetime
from datetime import time as time_type

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Availability(Base):
    __tablename__ = "availability"
    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_availability_employee_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_time: Mapped[time_type | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time_type | None] = mapped_column(Time, nullable=True)
    # Set once, at first submission for this (employee, date) pair — never
    # touched by an edit. This is exactly what "first to submit
    # availability" reads from for auto-reassignment ordering once shifts
    # exist (Section 10); the bulk-upsert deliberately excludes this column
    # from its DO UPDATE SET clause (see app/api/availability.py).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
