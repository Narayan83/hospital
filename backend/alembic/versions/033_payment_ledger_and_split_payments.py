"""payment modes ledger mapping and bill split payments

Revision ID: 033
Revises: 032
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_modes",
        sa.Column("ledger_id", sa.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        "fk_payment_modes_ledger_id",
        "payment_modes",
        "ledgers",
        ["ledger_id"],
        ["id"],
    )
    op.create_index(op.f("ix_payment_modes_ledger_id"), "payment_modes", ["ledger_id"], unique=False)

    op.create_table(
        "opd_bill_payments",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("payment_mode_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["opd_bills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_mode_id"], ["payment_modes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_opd_bill_payments_bill_id"), "opd_bill_payments", ["bill_id"], unique=False)

    op.create_table(
        "ipd_bill_payments",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("payment_mode_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["ipd_bills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_mode_id"], ["payment_modes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ipd_bill_payments_bill_id"), "ipd_bill_payments", ["bill_id"], unique=False)

    op.execute(
        """
        UPDATE payment_modes pm
        SET ledger_id = l.id, updated_at = now()
        FROM ledgers l
        WHERE pm.code = 'CASH' AND l.code = 'CASH'
          AND pm.ledger_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE payment_modes pm
        SET ledger_id = l.id, updated_at = now()
        FROM ledgers l
        WHERE pm.code = 'ONLINE' AND l.code = 'BANK-HDFC'
          AND pm.ledger_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE payment_modes pm
        SET ledger_id = l.id, updated_at = now()
        FROM ledgers l
        WHERE pm.code = 'SWIPE' AND l.code = 'BANK-ICICI'
          AND pm.ledger_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE payment_modes pm
        SET ledger_id = l.id, updated_at = now()
        FROM ledgers l
        WHERE pm.code = 'CREDIT' AND l.code = 'INSURANCE'
          AND pm.ledger_id IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO opd_bill_payments (
            id, bill_id, payment_mode_id, amount, sort_order, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            b.id,
            b.payment_mode_id,
            b.net_amount,
            0,
            true,
            now(),
            now()
        FROM opd_bills b
        WHERE b.payment_mode_id IS NOT NULL
          AND b.is_active = true
          AND NOT EXISTS (
              SELECT 1 FROM opd_bill_payments p WHERE p.bill_id = b.id
          )
        """
    )
    op.execute(
        """
        INSERT INTO ipd_bill_payments (
            id, bill_id, payment_mode_id, amount, sort_order, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            b.id,
            b.payment_mode_id,
            b.net_amount,
            0,
            true,
            now(),
            now()
        FROM ipd_bills b
        WHERE b.payment_mode_id IS NOT NULL
          AND b.is_active = true
          AND NOT EXISTS (
              SELECT 1 FROM ipd_bill_payments p WHERE p.bill_id = b.id
          )
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ipd_bill_payments_bill_id"), table_name="ipd_bill_payments")
    op.drop_table("ipd_bill_payments")
    op.drop_index(op.f("ix_opd_bill_payments_bill_id"), table_name="opd_bill_payments")
    op.drop_table("opd_bill_payments")
    op.drop_constraint("fk_payment_modes_ledger_id", "payment_modes", type_="foreignkey")
    op.drop_index(op.f("ix_payment_modes_ledger_id"), table_name="payment_modes")
    op.drop_column("payment_modes", "ledger_id")
