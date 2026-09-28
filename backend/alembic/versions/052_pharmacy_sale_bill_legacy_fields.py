"""pharmacy sale bill legacy fields

Revision ID: 052
Revises: 051
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "052"
down_revision: Union[str, None] = "051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pharmacy_sale_bills", sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=True))
    op.add_column("pharmacy_sale_bills", sa.Column("doctor_name", sa.String(length=150), nullable=True))
    op.add_column("pharmacy_sale_bills", sa.Column("scheme", sa.String(length=100), nullable=True))
    op.add_column(
        "pharmacy_sale_bills",
        sa.Column("round_off", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column("pharmacy_sale_bills", sa.Column("address1", sa.String(length=200), nullable=True))
    op.add_column("pharmacy_sale_bills", sa.Column("address2", sa.String(length=200), nullable=True))
    op.add_column("pharmacy_sale_bills", sa.Column("address3", sa.String(length=200), nullable=True))
    op.create_foreign_key(
        "fk_pharmacy_sale_bills_doctor_id",
        "pharmacy_sale_bills",
        "doctors",
        ["doctor_id"],
        ["id"],
    )

    op.add_column("pharmacy_sale_bill_lines", sa.Column("nos", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "pharmacy_sale_bill_lines",
        sa.Column("factor", sa.Numeric(8, 2), nullable=False, server_default="1"),
    )
    op.add_column("pharmacy_sale_bill_lines", sa.Column("batch_no", sa.String(length=50), nullable=True))
    op.add_column("pharmacy_sale_bill_lines", sa.Column("expiry_date", sa.Date(), nullable=True))
    op.add_column(
        "pharmacy_sale_bill_lines",
        sa.Column("tax_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "pharmacy_sale_bill_lines",
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "pharmacy_sale_bill_lines",
        sa.Column("line_discount_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "pharmacy_sale_bill_lines",
        sa.Column("line_discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "pharmacy_sale_bill_lines",
        sa.Column("line_net", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column("pharmacy_sale_bill_lines", sa.Column("user1", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("pharmacy_sale_bill_lines", "user1")
    op.drop_column("pharmacy_sale_bill_lines", "line_net")
    op.drop_column("pharmacy_sale_bill_lines", "line_discount_amount")
    op.drop_column("pharmacy_sale_bill_lines", "line_discount_percent")
    op.drop_column("pharmacy_sale_bill_lines", "tax_amount")
    op.drop_column("pharmacy_sale_bill_lines", "tax_percent")
    op.drop_column("pharmacy_sale_bill_lines", "expiry_date")
    op.drop_column("pharmacy_sale_bill_lines", "batch_no")
    op.drop_column("pharmacy_sale_bill_lines", "factor")
    op.drop_column("pharmacy_sale_bill_lines", "nos")
    op.drop_constraint("fk_pharmacy_sale_bills_doctor_id", "pharmacy_sale_bills", type_="foreignkey")
    op.drop_column("pharmacy_sale_bills", "address3")
    op.drop_column("pharmacy_sale_bills", "address2")
    op.drop_column("pharmacy_sale_bills", "address1")
    op.drop_column("pharmacy_sale_bills", "round_off")
    op.drop_column("pharmacy_sale_bills", "scheme")
    op.drop_column("pharmacy_sale_bills", "doctor_name")
    op.drop_column("pharmacy_sale_bills", "doctor_id")
