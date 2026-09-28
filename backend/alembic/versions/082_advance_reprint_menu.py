"""Add advance reprint menu under accounts.

Revision ID: 082
Revises: 081
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op

revision: str = "082"
down_revision: Union[str, None] = "081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO menus (
            id, code, label, parent_id, sort_order,
            legacy_mcode, legacy_form, parameters, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'advance_reprint',
            'Advance Reprint',
            parent.id,
            3,
            NULL,
            'ADVRP',
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'accounts'
          AND NOT EXISTS (
              SELECT 1 FROM menus WHERE code = 'advance_reprint'
          )
        """
    )

    op.execute(
        """
        UPDATE menus SET sort_order = 4
        WHERE code = 'adjustment_entry' AND parent_id IN (
            SELECT id FROM menus WHERE code = 'accounts'
        )
        """
    )
    op.execute(
        """
        UPDATE menus SET sort_order = 5
        WHERE code = 'receipt_voucher_adjustment_entry' AND parent_id IN (
            SELECT id FROM menus WHERE code = 'accounts'
        )
        """
    )
    op.execute(
        """
        UPDATE menus SET sort_order = 6
        WHERE code = 'ledger_details' AND parent_id IN (
            SELECT id FROM menus WHERE code = 'accounts'
        )
        """
    )
    op.execute(
        """
        UPDATE menus SET sort_order = 7
        WHERE code = 'cash_book' AND parent_id IN (
            SELECT id FROM menus WHERE code = 'accounts'
        )
        """
    )
    op.execute(
        """
        UPDATE menus SET sort_order = 8
        WHERE code = 'cashbook' AND parent_id IN (
            SELECT id FROM menus WHERE code = 'accounts'
        )
        """
    )
    op.execute(
        """
        UPDATE menus SET sort_order = 9
        WHERE code = 'daybook' AND parent_id IN (
            SELECT id FROM menus WHERE code = 'accounts'
        )
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
          AND m.code = 'advance_reprint'
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
        WHERE menu_id IN (
            SELECT id FROM menus WHERE code = 'advance_reprint'
        )
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'advance_reprint'")
