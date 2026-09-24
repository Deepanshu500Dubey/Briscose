"""add time_entries

Revision ID: f5a7d2c9b1e3
Revises: e4f6c1b3a5d9
Create Date: 2026-08-27 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f5a7d2c9b1e3'
down_revision: Union[str, None] = 'e4f6c1b3a5d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

time_entry_flag_enum = postgresql.ENUM(
    "none", "unscheduled", "early_start", "after_shift_end", name="time_entry_flag"
)


def upgrade() -> None:
    time_entry_flag_enum.create(op.get_bind(), checkfirst=True)
    time_entry_flag_enum.create_type = False

    op.create_table(
        "time_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("shift_id", sa.UUID(), nullable=True),
        sa.Column("clock_in", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("flag", time_entry_flag_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_time_entries_employee_id"), "time_entries", ["employee_id"], unique=False)

    # At most one open entry per employee — the DB-level line of defense
    # against double-clicks and multi-device use (Section 11).
    op.execute(
        """
        CREATE UNIQUE INDEX ux_time_entries_one_open_per_employee
        ON time_entries (employee_id)
        WHERE (clock_out IS NULL)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX ux_time_entries_one_open_per_employee")
    op.drop_index(op.f("ix_time_entries_employee_id"), table_name="time_entries")
    op.drop_table("time_entries")
    time_entry_flag_enum.drop(op.get_bind(), checkfirst=True)
