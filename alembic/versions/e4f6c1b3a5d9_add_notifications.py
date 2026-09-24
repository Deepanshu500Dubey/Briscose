"""add notifications

Revision ID: e4f6c1b3a5d9
Revises: d3e5b0a2f4c8
Create Date: 2026-08-27 08:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4f6c1b3a5d9'
down_revision: Union[str, None] = 'd3e5b0a2f4c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

notification_type_enum = postgresql.ENUM(
    "offer",
    "reassigned",
    "confirmed",
    "withdrawn",
    "shift_unfilled",
    "shift_dropped_below_minimum",
    name="notification_type",
)


def upgrade() -> None:
    notification_type_enum.create(op.get_bind(), checkfirst=True)
    # Already created explicitly above — without this, op.create_table's own
    # DDL event tries to CREATE TYPE again and fails with DuplicateObject.
    notification_type_enum.create_type = False

    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("type", notification_type_enum, nullable=False),
        sa.Column("shift_id", sa.UUID(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_table("notifications")
    notification_type_enum.drop(op.get_bind(), checkfirst=True)
