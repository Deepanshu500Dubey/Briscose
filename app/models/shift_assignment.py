"""ShiftAssignment model — an offer of a shift to an employee, and its
lifecycle (project blueprint, Section 7 & 10).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssignmentStatus(str, enum.Enum):
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    __table_args__ = (
        UniqueConstraint("shift_id", "employee_id", name="uq_shift_assignments_shift_employee"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        SAEnum(
            AssignmentStatus,
            name="assignment_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=AssignmentStatus.OFFERED,
    )
    # Null means system-generated — an auto-reassignment offer created by
    # reject_assignment(), not a manager's explicit action.
    offered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    offered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Denormalized from the parent shift at offer-creation time (shifts are
    # immutable once created in Phase 1 — no shift-edit endpoint exists yet).
    # This is what the overlap-prevention exclusion constraint below
    # actually enforces on: a naive (no-timezone) timestamp range in the
    # shift's own location-local time, good enough to catch the same
    # employee double-booked on two accepted shifts (Section 11). A
    # cross-location edge case where two different stores' local clocks
    # disagree isn't modeled — acceptable for Phase 1's single-country scope.
    shift_starts_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=False), nullable=False)
    shift_ends_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=False), nullable=False)
