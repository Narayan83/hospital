"""Add pathology bill cancel menu.

Revision ID: 080
Revises: 079
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op

revision: str = "080"
down_revision: Union[str, None] = "079"
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
            'pathology_bill_cancel',
            'Pathology Bill Cancel',
            parent.id,
            9,
            NULL,
            'PBLCL',
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'pathology'
          AND NOT EXISTS (
              SELECT 1 FROM menus WHERE code = 'pathology_bill_cancel'
          )
        """
    )

    # Keep notes master after cancel in the pathology menu order.
    op.execute(
        """
        UPDATE menus
        SET sort_order = 10
        WHERE code = 'pathology_notes_master'
          AND sort_order < 10
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
          AND m.code = 'pathology_bill_cancel'
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
            SELECT id FROM menus WHERE code = 'pathology_bill_cancel'
        )
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'pathology_bill_cancel'")
