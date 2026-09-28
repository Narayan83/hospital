"""unify modify bill menu under transactions after billing

Revision ID: 053
Revises: 052
Create Date: 2026-06-19

"""
from typing import Sequence, Union

from alembic import op

revision: str = "053"
down_revision: Union[str, None] = "052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY_MODIFY_CODES = (
    "bill_modification",
    "opd_bill_modification",
    "ipd_bill_modification",
    "pathology_bill_modification",
)


def upgrade() -> None:
    op.execute(
        """
        UPDATE menus child
        SET
            parent_id = transactions.id,
            sort_order = 2,
            label = 'Modify Bill',
            legacy_mcode = 105,
            legacy_form = 'MODIFYBL',
            is_active = true,
            updated_at = now()
        FROM menus transactions
        WHERE transactions.code = 'transactions'
          AND child.code = 'modify_bill'
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
            'modify_bill',
            'Modify Bill',
            transactions.id,
            2,
            105,
            'MODIFYBL',
            NULL,
            true,
            now(),
            now()
        FROM menus transactions
        WHERE transactions.code = 'transactions'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'modify_bill')
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
          AND m.code = 'modify_bill'
          AND NOT EXISTS (
              SELECT 1 FROM role_menu_permissions rp
              WHERE rp.role_id = r.id AND rp.menu_id = m.id
          )
        """
    )

    for code in _LEGACY_MODIFY_CODES:
        op.execute(
            f"""
            UPDATE menus
            SET is_active = false, updated_at = now()
            WHERE code = '{code}'
            """
        )


def downgrade() -> None:
    op.execute(
        """
        UPDATE menus
        SET
            parent_id = (SELECT id FROM menus WHERE code = 'transactions'),
            sort_order = 16,
            updated_at = now()
        WHERE code = 'modify_bill'
        """
    )

    op.execute(
        """
        UPDATE menus child
        SET
            parent_id = parent.id,
            is_active = true,
            updated_at = now()
        FROM menus parent
        WHERE parent.code = 'bill_modification'
          AND child.code IN (
              'bill_modification',
              'opd_bill_modification',
              'ipd_bill_modification',
              'pathology_bill_modification'
          )
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
            'bill_modification',
            'Bill Modification',
            transactions.id,
            2,
            NULL,
            NULL,
            NULL,
            true,
            now(),
            now()
        FROM menus transactions
        WHERE transactions.code = 'transactions'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'bill_modification')
        """
    )
