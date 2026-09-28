"""user types and user doctor mapping

Revision ID: 005
Revises: 004
Create Date: 2026-06-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_types",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("maps_to_doctor", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_types_code"), "user_types", ["code"], unique=True)

    op.add_column("users", sa.Column("user_type_id", sa.UUID(as_uuid=False), nullable=True))
    op.add_column("users", sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=True))
    op.create_foreign_key("fk_users_user_type_id", "users", "user_types", ["user_type_id"], ["id"])
    op.create_foreign_key("fk_users_doctor_id", "users", "doctors", ["doctor_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_users_doctor_id", "users", type_="foreignkey")
    op.drop_constraint("fk_users_user_type_id", "users", type_="foreignkey")
    op.drop_column("users", "doctor_id")
    op.drop_column("users", "user_type_id")
    op.drop_index(op.f("ix_user_types_code"), table_name="user_types")
    op.drop_table("user_types")
