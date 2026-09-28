"""pathology masters, orders and results

Revision ID: 029
Revises: 028
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathology_units",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pathology_units_code"), "pathology_units", ["code"], unique=True)

    op.create_table(
        "pathology_parameters",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("data_type", sa.String(length=20), nullable=False),
        sa.Column("method", sa.String(length=150), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["pathology_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pathology_parameters_code"), "pathology_parameters", ["code"], unique=True)

    op.create_table(
        "pathology_service_parameters",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("service_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("parameter_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parameter_id"], ["pathology_parameters.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["patient_service_masters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_id", "parameter_id", name="uq_pathology_service_parameter"),
    )
    op.create_index(
        op.f("ix_pathology_service_parameters_service_id"),
        "pathology_service_parameters",
        ["service_id"],
        unique=False,
    )

    op.create_table(
        "pathology_normal_ranges",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("parameter_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("gender", sa.String(length=1), nullable=False),
        sa.Column("age_from_days", sa.Integer(), nullable=False),
        sa.Column("age_to_days", sa.Integer(), nullable=False),
        sa.Column("min_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("max_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("text_range", sa.String(length=200), nullable=True),
        sa.Column("unit_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parameter_id"], ["pathology_parameters.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["pathology_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pathology_normal_ranges_parameter_id"),
        "pathology_normal_ranges",
        ["parameter_id"],
        unique=False,
    )

    op.create_table(
        "pathology_orders",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("patient_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("sample_date", sa.Date(), nullable=True),
        sa.Column("sample_no", sa.String(length=30), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("pathologist_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["pathology_bills.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["pathologist_id"], ["doctors.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bill_id", name="uq_pathology_order_per_bill"),
    )
    op.create_index(op.f("ix_pathology_orders_bill_id"), "pathology_orders", ["bill_id"], unique=False)
    op.create_index(op.f("ix_pathology_orders_patient_id"), "pathology_orders", ["patient_id"], unique=False)

    op.create_table(
        "pathology_results",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("order_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_line_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("parameter_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("service_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("result_value", sa.String(length=200), nullable=True),
        sa.Column("result_numeric", sa.Numeric(12, 4), nullable=True),
        sa.Column("unit_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("reference_range_text", sa.String(length=200), nullable=True),
        sa.Column("is_abnormal", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bill_line_id"], ["pathology_bill_lines.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["pathology_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parameter_id"], ["pathology_parameters.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["patient_service_masters.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["pathology_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pathology_results_order_id"), "pathology_results", ["order_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pathology_results_order_id"), table_name="pathology_results")
    op.drop_table("pathology_results")
    op.drop_index(op.f("ix_pathology_orders_patient_id"), table_name="pathology_orders")
    op.drop_index(op.f("ix_pathology_orders_bill_id"), table_name="pathology_orders")
    op.drop_table("pathology_orders")
    op.drop_index(op.f("ix_pathology_normal_ranges_parameter_id"), table_name="pathology_normal_ranges")
    op.drop_table("pathology_normal_ranges")
    op.drop_index(op.f("ix_pathology_service_parameters_service_id"), table_name="pathology_service_parameters")
    op.drop_table("pathology_service_parameters")
    op.drop_index(op.f("ix_pathology_parameters_code"), table_name="pathology_parameters")
    op.drop_table("pathology_parameters")
    op.drop_index(op.f("ix_pathology_units_code"), table_name="pathology_units")
    op.drop_table("pathology_units")
