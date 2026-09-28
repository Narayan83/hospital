"""hospital profile menu and permissions

Revision ID: 037
Revises: 036
Create Date: 2026-06-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "037"
down_revision: Union[str, None] = "036"
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
            'hospital_profile',
            'Hospital Profile',
            parent.id,
            44,
            95,
            'CMASTER',
            'HP',
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'masters'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'hospital_profile')
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
          AND m.code = 'hospital_profile'
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
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'hospital_profile')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'hospital_profile'")
