"""add roles, locations, and refresh tokens

Revision ID: a91f2c7d3b6e
Revises: 3c5364df1a1b
Create Date: 2026-08-27 06:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a91f2c7d3b6e'
down_revision: Union[str, None] = '3c5364df1a1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role_enum = postgresql.ENUM("employee", "manager", "admin", name="user_role")


def upgrade() -> None:
    # Enabled now, ahead of the overlap-prevention exclusion constraint that
    # will use it once shifts land (see the project blueprint, Section 11) —
    # cheaper to add while the schema is still small than to retrofit later.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "locations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    user_role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "role", user_role_enum, nullable=False, server_default="employee"
        ),
    )
    op.add_column(
        "users",
        sa.Column("home_location_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_users_home_location_id_locations",
        "users",
        "locations",
        ["home_location_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "manager_locations",
        sa.Column("manager_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("manager_id", "location_id"),
    )

    op.create_table(
        "employee_locations",
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("employee_id", "location_id"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_refresh_tokens_token_hash"), "refresh_tokens", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_token_hash"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_table("employee_locations")
    op.drop_table("manager_locations")

    op.drop_constraint("fk_users_home_location_id_locations", "users", type_="foreignkey")
    op.drop_column("users", "token_version")
    op.drop_column("users", "home_location_id")
    op.drop_column("users", "role")
    user_role_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_table("locations")

    op.execute("DROP EXTENSION IF EXISTS btree_gist")
