"""single service opd billing options and bills

Revision ID: 094
Revises: 093
Create Date: 2026-09-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "094"
down_revision: Union[str, None] = "093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "single_service_opd_options",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("menu_code", sa.String(length=80), nullable=False),
        sa.Column("service_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("service_name", sa.String(length=200), nullable=False),
        sa.Column("use_patient_id", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_rate", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("bill_prefix", sa.String(length=10), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["patient_service_masters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("menu_code"),
    )
    op.create_index(
        op.f("ix_single_service_opd_options_menu_code"),
        "single_service_opd_options",
        ["menu_code"],
        unique=True,
    )

    op.create_table(
        "single_service_opd_bills",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_no", sa.String(length=40), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("option_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("patient_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("patient_no", sa.String(length=30), nullable=True),
        sa.Column("patient_name", sa.String(length=200), nullable=False),
        sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("service_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("service_name", sa.String(length=200), nullable=False),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_mode_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("payment_mode_name", sa.String(length=150), nullable=False, server_default="Cash"),
        sa.Column("created_by_user_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["option_id"], ["single_service_opd_options.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["payment_mode_id"], ["payment_modes.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["patient_service_masters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bill_no"),
    )
    op.create_index(
        op.f("ix_single_service_opd_bills_bill_no"),
        "single_service_opd_bills",
        ["bill_no"],
        unique=True,
    )
    op.create_index(
        op.f("ix_single_service_opd_bills_bill_date"),
        "single_service_opd_bills",
        ["bill_date"],
    )
    op.create_index(
        op.f("ix_single_service_opd_bills_option_id"),
        "single_service_opd_bills",
        ["option_id"],
    )
    op.create_index(
        op.f("ix_single_service_opd_bills_patient_id"),
        "single_service_opd_bills",
        ["patient_id"],
    )
    op.create_index(
        op.f("ix_single_service_opd_bills_doctor_id"),
        "single_service_opd_bills",
        ["doctor_id"],
    )
    op.create_index(
        op.f("ix_single_service_opd_bills_created_by_user_id"),
        "single_service_opd_bills",
        ["created_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_single_service_opd_bills_created_by_user_id"), table_name="single_service_opd_bills")
    op.drop_index(op.f("ix_single_service_opd_bills_doctor_id"), table_name="single_service_opd_bills")
    op.drop_index(op.f("ix_single_service_opd_bills_patient_id"), table_name="single_service_opd_bills")
    op.drop_index(op.f("ix_single_service_opd_bills_option_id"), table_name="single_service_opd_bills")
    op.drop_index(op.f("ix_single_service_opd_bills_bill_date"), table_name="single_service_opd_bills")
    op.drop_index(op.f("ix_single_service_opd_bills_bill_no"), table_name="single_service_opd_bills")
    op.drop_table("single_service_opd_bills")
    op.drop_index(
        op.f("ix_single_service_opd_options_menu_code"),
        table_name="single_service_opd_options",
    )
    op.drop_table("single_service_opd_options")
