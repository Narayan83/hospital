"""ipd admissions

Revision ID: 020
Revises: 019
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ipd_admissions",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("admission_no", sa.String(length=30), nullable=False),
        sa.Column("admission_date", sa.Date(), nullable=False),
        sa.Column("patient_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("ward_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("department_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("bed_no", sa.String(length=30), nullable=True),
        sa.Column("advance_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("diagnosis", sa.String(length=250), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["ward_id"], ["wards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ipd_admissions_admission_no"), "ipd_admissions", ["admission_no"], unique=True)
    op.create_index(op.f("ix_ipd_admissions_patient_id"), "ipd_admissions", ["patient_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ipd_admissions_patient_id"), table_name="ipd_admissions")
    op.drop_index(op.f("ix_ipd_admissions_admission_no"), table_name="ipd_admissions")
    op.drop_table("ipd_admissions")
