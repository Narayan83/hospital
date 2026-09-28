"""cashbook vouchers and ledger posting

Revision ID: 043
Revises: 042
Create Date: 2026-06-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cashbook_vouchers",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("voucher_no", sa.String(length=40), nullable=False),
        sa.Column("voucher_date", sa.Date(), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("patient_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("patient_no", sa.String(length=20), nullable=True),
        sa.Column("narration", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cashbook_vouchers_voucher_no"), "cashbook_vouchers", ["voucher_no"], unique=False)
    op.create_index(op.f("ix_cashbook_vouchers_voucher_date"), "cashbook_vouchers", ["voucher_date"], unique=False)
    op.create_index(op.f("ix_cashbook_vouchers_source_type"), "cashbook_vouchers", ["source_type"], unique=False)
    op.create_index(op.f("ix_cashbook_vouchers_source_id"), "cashbook_vouchers", ["source_id"], unique=False)
    op.create_index(op.f("ix_cashbook_vouchers_patient_id"), "cashbook_vouchers", ["patient_id"], unique=False)

    op.create_table(
        "cashbook_voucher_lines",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("voucher_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("ledger_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("debit_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("credit_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
        sa.ForeignKeyConstraint(["voucher_id"], ["cashbook_vouchers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cashbook_voucher_lines_voucher_id"),
        "cashbook_voucher_lines",
        ["voucher_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cashbook_voucher_lines_ledger_id"),
        "cashbook_voucher_lines",
        ["ledger_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO ledgers (id, code, name, sort_order, is_active, created_at, updated_at)
        SELECT gen_random_uuid(), 'PATIENT-ACCOUNT', 'Patient Account Ledger', 17, true, now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM ledgers WHERE code = 'PATIENT-ACCOUNT')
        """
    )

    op.execute(
        """
        INSERT INTO menus (
            id, code, label, parent_id, sort_order,
            legacy_mcode, legacy_form, parameters, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'cashbook',
            'Cashbook / Ledger View',
            parent.id,
            2,
            NULL,
            'CASHBOOK',
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'reports'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'cashbook')
        """
    )

    op.execute(
        """
        INSERT INTO role_menu_permissions (
            id, role_id, menu_id, can_view, can_create, can_update, can_delete,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            r.id,
            m.id,
            true, true, true, true,
            now(), now()
        FROM roles r
        CROSS JOIN menus m
        WHERE r.role_name = 'Super Admin'
          AND m.code = 'cashbook'
          AND NOT EXISTS (
              SELECT 1 FROM role_menu_permissions rp
              WHERE rp.role_id = r.id AND rp.menu_id = m.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_menu_permissions
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'cashbook')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'cashbook'")
    op.drop_index(op.f("ix_cashbook_voucher_lines_ledger_id"), table_name="cashbook_voucher_lines")
    op.drop_index(op.f("ix_cashbook_voucher_lines_voucher_id"), table_name="cashbook_voucher_lines")
    op.drop_table("cashbook_voucher_lines")
    op.drop_index(op.f("ix_cashbook_vouchers_patient_id"), table_name="cashbook_vouchers")
    op.drop_index(op.f("ix_cashbook_vouchers_source_id"), table_name="cashbook_vouchers")
    op.drop_index(op.f("ix_cashbook_vouchers_source_type"), table_name="cashbook_vouchers")
    op.drop_index(op.f("ix_cashbook_vouchers_voucher_date"), table_name="cashbook_vouchers")
    op.drop_index(op.f("ix_cashbook_vouchers_voucher_no"), table_name="cashbook_vouchers")
    op.drop_table("cashbook_vouchers")
    op.execute("DELETE FROM ledgers WHERE code = 'PATIENT-ACCOUNT'")
