"""Move accounting menus under Accounts main head



Revision ID: 078

Revises: 077

Create Date: 2026-07-17



"""

from typing import Sequence, Union



from alembic import op



revision: str = "078"

down_revision: Union[str, None] = "077"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None



# (code, label, sort_order)

ACCOUNT_CHILDREN = [

    ("ledger_master", "Ledger Master", 1),

    ("advance_collection", "Advance Collection", 2),

    ("adjustment_entry", "Payment / Adjustment Entry", 3),

    ("receipt_voucher_adjustment_entry", "Contra Entry", 4),

    ("ledger_details", "Ledger Details", 5),

    ("cash_book", "Cash Book", 6),

    ("cashbook", "Cashbook / Ledger View", 7),

    ("daybook", "Daybook", 8),

]





def upgrade() -> None:

    op.execute(

        """

        INSERT INTO menus (

            id, code, label, parent_id, sort_order,

            legacy_mcode, legacy_form, parameters, is_active, created_at, updated_at

        )

        SELECT

            gen_random_uuid(),

            'accounts',

            'Accounts',

            NULL,

            25,

            NULL,

            NULL,

            NULL,

            true,

            now(),

            now()

        WHERE NOT EXISTS (SELECT 1 FROM menus WHERE code = 'accounts')

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

          AND m.code = 'accounts'

          AND NOT EXISTS (

              SELECT 1 FROM role_menu_permissions rp

              WHERE rp.role_id = r.id AND rp.menu_id = m.id

          )

        """

    )



    for code, label, sort_order in ACCOUNT_CHILDREN:

        op.execute(

            f"""

            UPDATE menus

            SET parent_id = (SELECT id FROM menus WHERE code = 'accounts'),

                label = '{label}',

                sort_order = {sort_order},

                is_active = true,

                updated_at = now()

            WHERE code = '{code}'

            """

        )





def downgrade() -> None:

    # Move children back to previous parents

    restores = [

        ("ledger_master", "masters", 39),

        ("advance_collection", "transactions", 6),

        ("adjustment_entry", "transactions", 7),

        ("receipt_voucher_adjustment_entry", "transactions", 18),

        ("ledger_details", "reports", 3),

        ("cash_book", "reports", 4),

        ("cashbook", "reports", 2),

        ("daybook", "reports", 5),

    ]

    for code, parent_code, sort_order in restores:

        op.execute(

            f"""

            UPDATE menus

            SET parent_id = (SELECT id FROM menus WHERE code = '{parent_code}'),

                sort_order = {sort_order},

                updated_at = now()

            WHERE code = '{code}'

            """

        )

    op.execute(

        """

        DELETE FROM role_menu_permissions

        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'accounts')

        """

    )

    op.execute("DELETE FROM menus WHERE code = 'accounts'")


