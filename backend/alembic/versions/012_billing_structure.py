"""procedure types and billing structure mappings

Revision ID: 012
Revises: 011
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "procedure_types",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_procedure_types_code"), "procedure_types", ["code"], unique=True)

    op.create_table(
        "billing_structure_mappings",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("billing_type_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("department_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("procedure_type_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["billing_type_id"], ["billing_types.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["procedure_type_id"], ["procedure_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "billing_type_id",
            "department_id",
            "procedure_type_id",
            name="uq_billing_structure_combo",
        ),
    )
    op.create_index(
        op.f("ix_billing_structure_mappings_billing_type_id"),
        "billing_structure_mappings",
        ["billing_type_id"],
    )
    op.create_index(
        op.f("ix_billing_structure_mappings_department_id"),
        "billing_structure_mappings",
        ["department_id"],
    )
    op.create_index(
        op.f("ix_billing_structure_mappings_procedure_type_id"),
        "billing_structure_mappings",
        ["procedure_type_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_billing_structure_mappings_procedure_type_id"),
        table_name="billing_structure_mappings",
    )
    op.drop_index(
        op.f("ix_billing_structure_mappings_department_id"),
        table_name="billing_structure_mappings",
    )
    op.drop_index(
        op.f("ix_billing_structure_mappings_billing_type_id"),
        table_name="billing_structure_mappings",
    )
    op.drop_table("billing_structure_mappings")
    op.drop_index(op.f("ix_procedure_types_code"), table_name="procedure_types")
    op.drop_table("procedure_types")
