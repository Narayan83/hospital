"""ipd discharge summaries

Revision ID: 044
Revises: 043
Create Date: 2026-06-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ipd_discharge_summaries",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("summary_no", sa.String(length=30), nullable=False),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("admission_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("patient_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("chief_complaint", sa.Text(), nullable=True),
        sa.Column("history_of_illness", sa.Text(), nullable=True),
        sa.Column("diagnosis_on_admission", sa.String(length=500), nullable=True),
        sa.Column("final_diagnosis", sa.String(length=500), nullable=True),
        sa.Column("investigation", sa.Text(), nullable=True),
        sa.Column("treatment_given", sa.Text(), nullable=True),
        sa.Column("procedures", sa.Text(), nullable=True),
        sa.Column("condition_on_discharge", sa.String(length=100), nullable=True),
        sa.Column("medications_on_discharge", sa.Text(), nullable=True),
        sa.Column("advice_follow_up", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["admission_id"], ["ipd_admissions.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("admission_id"),
    )
    op.create_index(
        op.f("ix_ipd_discharge_summaries_summary_no"),
        "ipd_discharge_summaries",
        ["summary_no"],
        unique=True,
    )
    op.create_index(
        op.f("ix_ipd_discharge_summaries_admission_id"),
        "ipd_discharge_summaries",
        ["admission_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ipd_discharge_summaries_patient_id"),
        "ipd_discharge_summaries",
        ["patient_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ipd_discharge_summaries_patient_id"), table_name="ipd_discharge_summaries")
    op.drop_index(op.f("ix_ipd_discharge_summaries_admission_id"), table_name="ipd_discharge_summaries")
    op.drop_index(op.f("ix_ipd_discharge_summaries_summary_no"), table_name="ipd_discharge_summaries")
    op.drop_table("ipd_discharge_summaries")
