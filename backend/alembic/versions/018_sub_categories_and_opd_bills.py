"""service sub categories and opd bills

Revision ID: 018
Revises: 017
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "service_sub_categories",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("category_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["service_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category_id", "code", name="uq_sub_category_per_category"),
    )
    op.create_index(
        op.f("ix_service_sub_categories_category_id"),
        "service_sub_categories",
        ["category_id"],
        unique=False,
    )

    op.add_column(
        "patient_service_masters",
        sa.Column("sub_category_id", sa.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        "fk_patient_service_masters_sub_category_id",
        "patient_service_masters",
        "service_sub_categories",
        ["sub_category_id"],
        ["id"],
    )

    op.create_table(
        "opd_bills",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_no", sa.String(length=30), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("patient_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("payment_mode_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("department_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("is_cash", sa.Boolean(), nullable=False),
        sa.Column("scheme", sa.String(length=100), nullable=True),
        sa.Column("admin_charges", sa.Numeric(12, 2), nullable=False),
        sa.Column("scheme_discount", sa.Numeric(12, 2), nullable=False),
        sa.Column("sanctioned_scheme_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("adjust_advance", sa.Numeric(12, 2), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["payment_mode_id"], ["payment_modes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opd_bills_bill_no"), "opd_bills", ["bill_no"], unique=True)
    op.create_index(op.f("ix_opd_bills_patient_id"), "opd_bills", ["patient_id"], unique=False)

    op.create_table(
        "opd_bill_lines",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("service_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("service_code", sa.String(length=30), nullable=False),
        sa.Column("service_name", sa.String(length=200), nullable=False),
        sa.Column("category_name", sa.String(length=150), nullable=True),
        sa.Column("sub_category_name", sa.String(length=150), nullable=True),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_source", sa.String(length=20), nullable=False),
        sa.Column("package_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["opd_bills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["package_id"], ["billing_packages.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["patient_service_masters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opd_bill_lines_bill_id"), "opd_bill_lines", ["bill_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_opd_bill_lines_bill_id"), table_name="opd_bill_lines")
    op.drop_table("opd_bill_lines")
    op.drop_index(op.f("ix_opd_bills_patient_id"), table_name="opd_bills")
    op.drop_index(op.f("ix_opd_bills_bill_no"), table_name="opd_bills")
    op.drop_table("opd_bills")
    op.drop_constraint("fk_patient_service_masters_sub_category_id", "patient_service_masters", type_="foreignkey")
    op.drop_column("patient_service_masters", "sub_category_id")
    op.drop_index(op.f("ix_service_sub_categories_category_id"), table_name="service_sub_categories")
    op.drop_table("service_sub_categories")
