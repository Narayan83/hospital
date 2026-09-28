"""pathology bill reprint and modify menus

Revision ID: 041
Revises: 040
Create Date: 2026-06-14

"""
from typing import Sequence, Union

from alembic import op

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insert_menu(code: str, label: str, parent_code: str, sort_order: int, legacy_form: str) -> None:
    op.execute(
        f"""
        INSERT INTO menus (
            id, code, label, parent_id, sort_order,
            legacy_mcode, legacy_form, parameters, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            '{code}',
            '{label}',
            parent.id,
            {sort_order},
            NULL,
            '{legacy_form}',
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = '{parent_code}'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = '{code}')
        """
    )
    op.execute(
        f"""
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
          AND m.code = '{code}'
          AND NOT EXISTS (
              SELECT 1 FROM role_menu_permissions rp
              WHERE rp.role_id = r.id AND rp.menu_id = m.id
          )
        """
    )


def upgrade() -> None:
    _insert_menu("pathology_bill_reprint", "Pathology Bill Reprint", "pathology", 7, "PBLRP")
    _insert_menu(
        "pathology_bill_modification",
        "Pathology Bill Modification",
        "bill_modification",
        3,
        "PBLMOD",
    )


def downgrade() -> None:
    for code in ("pathology_bill_modification", "pathology_bill_reprint"):
        op.execute(
            f"""
            DELETE FROM role_menu_permissions
            WHERE menu_id IN (SELECT id FROM menus WHERE code = '{code}')
            """
        )
        op.execute(f"DELETE FROM menus WHERE code = '{code}'")
