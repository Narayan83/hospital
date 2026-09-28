"""service categories and billing packages

Revision ID: 016
Revises: 015
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "service_categories",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_service_categories_code"), "service_categories", ["code"], unique=True)

    op.create_table(
        "billing_packages",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("package_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_billing_packages_code"), "billing_packages", ["code"], unique=True)

    op.add_column(
        "patient_service_masters",
        sa.Column("category_id", sa.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        "fk_patient_service_masters_category_id",
        "patient_service_masters",
        "service_categories",
        ["category_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_patient_service_masters_category_id"),
        "patient_service_masters",
        ["category_id"],
        unique=False,
    )

    op.create_table(
        "billing_package_items",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("package_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("service_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("rate_override", sa.Numeric(12, 2), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["package_id"], ["billing_packages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_id"], ["patient_service_masters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("package_id", "service_id", name="uq_package_service"),
    )
    op.create_index(
        op.f("ix_billing_package_items_package_id"),
        "billing_package_items",
        ["package_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_package_items_service_id"),
        "billing_package_items",
        ["service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_billing_package_items_service_id"), table_name="billing_package_items")
    op.drop_index(op.f("ix_billing_package_items_package_id"), table_name="billing_package_items")
    op.drop_table("billing_package_items")
    op.drop_index(op.f("ix_patient_service_masters_category_id"), table_name="patient_service_masters")
    op.drop_constraint("fk_patient_service_masters_category_id", "patient_service_masters", type_="foreignkey")
    op.drop_column("patient_service_masters", "category_id")
    op.drop_index(op.f("ix_billing_packages_code"), table_name="billing_packages")
    op.drop_table("billing_packages")
    op.drop_index(op.f("ix_service_categories_code"), table_name="service_categories")
    op.drop_table("service_categories")
