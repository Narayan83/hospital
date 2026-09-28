"""pathology bills

Revision ID: 028
Revises: 027
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathology_bills",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_no", sa.String(length=30), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("patient_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("referring_doctor", sa.String(length=150), nullable=True),
        sa.Column("payment_mode_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("department_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("is_cash", sa.Boolean(), nullable=False),
        sa.Column("scheme", sa.String(length=100), nullable=True),
        sa.Column("admin_charges", sa.Numeric(12, 2), nullable=False),
        sa.Column("scheme_discount", sa.Numeric(12, 2), nullable=False),
        sa.Column("adjust_advance", sa.Numeric(12, 2), nullable=False),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["payment_mode_id"], ["payment_modes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pathology_bills_bill_no"), "pathology_bills", ["bill_no"], unique=True
    )
    op.create_index(
        op.f("ix_pathology_bills_patient_id"), "pathology_bills", ["patient_id"], unique=False
    )

    op.create_table(
        "pathology_bill_lines",
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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["bill_id"], ["pathology_bills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["package_id"], ["billing_packages.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["patient_service_masters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pathology_bill_lines_bill_id"),
        "pathology_bill_lines",
        ["bill_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pathology_bill_lines_bill_id"), table_name="pathology_bill_lines")
    op.drop_table("pathology_bill_lines")
    op.drop_index(op.f("ix_pathology_bills_patient_id"), table_name="pathology_bills")
    op.drop_index(op.f("ix_pathology_bills_bill_no"), table_name="pathology_bills")
    op.drop_table("pathology_bills")
