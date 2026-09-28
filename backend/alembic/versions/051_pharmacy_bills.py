"""pharmacy sale and purchase bills

Revision ID: 051
Revises: 050
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "051"
down_revision: Union[str, None] = "050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pharmacy_sale_bills",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_no", sa.String(length=30), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("patient_name", sa.String(length=200), nullable=True),
        sa.Column("payment_mode_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("is_cash", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="saved"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["payment_mode_id"], ["payment_modes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bill_no"),
    )
    op.create_index("ix_pharmacy_sale_bills_bill_no", "pharmacy_sale_bills", ["bill_no"])
    op.create_index("ix_pharmacy_sale_bills_patient_id", "pharmacy_sale_bills", ["patient_id"])

    op.create_table(
        "pharmacy_sale_bill_lines",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("item_code", sa.String(length=30), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("schedule", sa.String(length=10), nullable=True),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["pharmacy_sale_bills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["pharmacy_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pharmacy_sale_bill_lines_bill_id", "pharmacy_sale_bill_lines", ["bill_id"])

    op.create_table(
        "pharmacy_purchase_bills",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_no", sa.String(length=30), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("invoice_no", sa.String(length=50), nullable=True),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="saved"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["pharmacy_suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bill_no"),
    )
    op.create_index("ix_pharmacy_purchase_bills_bill_no", "pharmacy_purchase_bills", ["bill_no"])
    op.create_index("ix_pharmacy_purchase_bills_supplier_id", "pharmacy_purchase_bills", ["supplier_id"])

    op.create_table(
        "pharmacy_purchase_bill_lines",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("item_code", sa.String(length=30), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("batch_no", sa.String(length=50), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["pharmacy_purchase_bills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["pharmacy_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pharmacy_purchase_bill_lines_bill_id", "pharmacy_purchase_bill_lines", ["bill_id"])

    op.execute(
        sa.text(
            """
            INSERT INTO pharmacy_items (
                id, item_type, code, name, generic_name, unit, mrp, purchase_rate, sale_rate, schedule, sort_order
            )
            SELECT gen_random_uuid(), 'MD', 'PCM500', 'Paracetamol 500mg', 'Paracetamol', 'Tab', 2.00, 1.20, 2.00, 'OTC', 1
            WHERE NOT EXISTS (
                SELECT 1 FROM pharmacy_items WHERE item_type = 'MD' AND code = 'PCM500'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO pharmacy_items (
                id, item_type, code, name, generic_name, unit, mrp, purchase_rate, sale_rate, schedule, sort_order
            )
            SELECT gen_random_uuid(), 'MD', 'AMOX250', 'Amoxicillin 250mg', 'Amoxicillin', 'Cap', 8.00, 5.00, 8.00, 'H', 2
            WHERE NOT EXISTS (
                SELECT 1 FROM pharmacy_items WHERE item_type = 'MD' AND code = 'AMOX250'
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_table("pharmacy_purchase_bill_lines")
    op.drop_table("pharmacy_purchase_bills")
    op.drop_table("pharmacy_sale_bill_lines")
    op.drop_table("pharmacy_sale_bills")
