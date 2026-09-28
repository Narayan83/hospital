"""patient service masters

Revision ID: 015
Revises: 014
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_service_masters",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("service_charge", sa.Numeric(12, 2), nullable=False),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_sharing", sa.Boolean(), nullable=False),
        sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("discount_apply", sa.Boolean(), nullable=False),
        sa.Column("is_renewal", sa.Boolean(), nullable=False),
        sa.Column("renewal_days", sa.Integer(), nullable=True),
        sa.Column("is_service_active", sa.Boolean(), nullable=False),
        sa.Column("close_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_patient_service_masters_code"),
        "patient_service_masters",
        ["code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_patient_service_masters_code"), table_name="patient_service_masters")
    op.drop_table("patient_service_masters")
