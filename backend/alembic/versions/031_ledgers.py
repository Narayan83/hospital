"""ledger master

Revision ID: 031
Revises: 030
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ledgers",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ledgers_code"), "ledgers", ["code"], unique=True)

    op.execute(
        """
        INSERT INTO menus (
            id, code, label, parent_id, sort_order,
            legacy_mcode, legacy_form, parameters, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'ledger_master',
            'Ledger Master',
            parent.id,
            39,
            82,
            'LEDGMSTR',
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'masters'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'ledger_master')
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
          AND m.code = 'ledger_master'
          AND NOT EXISTS (
              SELECT 1 FROM role_menu_permissions rp
              WHERE rp.role_id = r.id AND rp.menu_id = m.id
          )
        """
    )

    op.execute(
        """
        UPDATE menus
        SET is_active = false,
            updated_at = now()
        WHERE code = 'general_ledger_creation'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE menus
        SET is_active = true,
            updated_at = now()
        WHERE code = 'general_ledger_creation'
        """
    )
    op.execute(
        """
        DELETE FROM role_menu_permissions
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'ledger_master')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'ledger_master'")
    op.drop_index(op.f("ix_ledgers_code"), table_name="ledgers")
    op.drop_table("ledgers")
