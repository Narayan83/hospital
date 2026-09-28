"""Add IPD Bill Reprint menu under Billing.

Revision ID: 090
Revises: 089
Create Date: 2026-08-08
"""

from typing import Sequence, Union

from alembic import op

revision: str = "090"
down_revision: Union[str, None] = "089"
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
            'ipd_bill_reprint',
            'IPD Bill Reprint',
            parent.id,
            4,
            NULL,
            'IPBLRP',
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'billing'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'ipd_bill_reprint')
        """
    )

    op.execute(
        """
        UPDATE menus SET sort_order = 5
        WHERE code = 'in_patient_admission' AND sort_order < 5
        """
    )
    op.execute(
        """
        UPDATE menus SET sort_order = 6
        WHERE code = 'in_patient_discharge' AND sort_order < 6
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
          AND m.code = 'ipd_bill_reprint'
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
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'ipd_bill_reprint')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'ipd_bill_reprint'")
