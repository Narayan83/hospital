"""bill modification menus

Revision ID: 040
Revises: 039
Create Date: 2026-06-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insert_menu(code: str, label: str, parent_code: str, sort_order: int, legacy_form: str | None) -> None:
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
            {f"'{legacy_form}'" if legacy_form else 'NULL'},
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
    _insert_menu("bill_modification", "Bill Modification", "transactions", 2, None)
    _insert_menu("opd_bill_modification", "OPD Bill Modification", "bill_modification", 1, "OPBLMOD")
    _insert_menu("ipd_bill_modification", "IPD Bill Modification", "bill_modification", 2, "IPBLMOD")


def downgrade() -> None:
    for code in ("ipd_bill_modification", "opd_bill_modification", "bill_modification"):
        op.execute(
            f"""
            DELETE FROM role_menu_permissions
            WHERE menu_id IN (SELECT id FROM menus WHERE code = '{code}')
            """
        )
        op.execute(f"DELETE FROM menus WHERE code = '{code}'")
