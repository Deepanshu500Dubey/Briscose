"""add shifts and shift_assignments

Revision ID: d3e5b0a2f4c8
Revises: c2d4a8f1e9b7
Create Date: 2026-08-27 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd3e5b0a2f4c8'
down_revision: Union[str, None] = 'c2d4a8f1e9b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

shift_status_enum = postgresql.ENUM(
    "open", "pending_acceptance", "confirmed", "unfilled", "cancelled", name="shift_status"
)
assignment_status_enum = postgresql.ENUM(
    "offered", "accepted", "rejected", "withdrawn", name="assignment_status"
)


def upgrade() -> None:
    shift_status_enum.create(op.get_bind(), checkfirst=True)
    assignment_status_enum.create(op.get_bind(), checkfirst=True)
    # Already created explicitly above — without this, op.create_table's own
    # DDL event tries to CREATE TYPE again and fails with DuplicateObject.
    shift_status_enum.create_type = False
    assignment_status_enum.create_type = False

    op.create_table(
        "shifts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("min_staff", sa.Integer(), nullable=False),
        sa.Column("max_staff", sa.Integer(), nullable=False),
        sa.Column("status", shift_status_enum, nullable=False),
        sa.Column("roster_locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("min_staff <= max_staff", name="ck_shifts_min_le_max_staff"),
        sa.CheckConstraint("start_time < end_time", name="ck_shifts_start_before_end"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shifts_location_id"), "shifts", ["location_id"], unique=False)
    op.create_index(op.f("ix_shifts_date"), "shifts", ["date"], unique=False)

    op.create_table(
        "shift_assignments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("shift_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("status", assignment_status_enum, nullable=False),
        sa.Column("offered_by", sa.UUID(), nullable=True),
        sa.Column("offered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shift_starts_at", sa.TIMESTAMP(timezone=False), nullable=False),
        sa.Column("shift_ends_at", sa.TIMESTAMP(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["offered_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shift_id", "employee_id", name="uq_shift_assignments_shift_employee"),
    )
    op.create_index(
        op.f("ix_shift_assignments_shift_id"), "shift_assignments", ["shift_id"], unique=False
    )
    op.create_index(
        op.f("ix_shift_assignments_employee_id"), "shift_assignments", ["employee_id"], unique=False
    )

    # Overlap prevention (Section 11): the same employee can never hold two
    # ACCEPTED assignments whose shift time ranges overlap. Uses btree_gist
    # (enabled in a prior migration) for the uuid equality operator class
    # inside a GiST exclusion constraint.
    op.execute(
        """
        ALTER TABLE shift_assignments
        ADD CONSTRAINT ux_shift_assignments_no_overlap_when_accepted
        EXCLUDE USING gist (
            employee_id WITH =,
            tsrange(shift_starts_at, shift_ends_at, '[)') WITH &&
        )
        WHERE (status = 'accepted')
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE shift_assignments DROP CONSTRAINT ux_shift_assignments_no_overlap_when_accepted"
    )
    op.drop_index(op.f("ix_shift_assignments_employee_id"), table_name="shift_assignments")
    op.drop_index(op.f("ix_shift_assignments_shift_id"), table_name="shift_assignments")
    op.drop_table("shift_assignments")

    op.drop_index(op.f("ix_shifts_date"), table_name="shifts")
    op.drop_index(op.f("ix_shifts_location_id"), table_name="shifts")
    op.drop_table("shifts")

    assignment_status_enum.drop(op.get_bind(), checkfirst=True)
    shift_status_enum.drop(op.get_bind(), checkfirst=True)
