"""accounting menus and voucher support



Revision ID: 077

Revises: 076

Create Date: 2026-07-17



"""

from typing import Sequence, Union



from alembic import op



revision: str = "077"

down_revision: Union[str, None] = "076"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None



NEW_MENUS = [

    ("advance_collection", "Advance Collection", "transactions", 6, None, "ADVCOLL"),

    ("ledger_details", "Ledger Details", "reports", 3, None, "LEDGDET"),

    ("cash_book", "Cash Book", "reports", 4, None, "CASHBK"),

    ("daybook", "Daybook", "reports", 5, None, "DAYBOOK"),

]





def upgrade() -> None:

    for code, label, parent_code, sort_order, legacy_mcode, legacy_form in NEW_MENUS:

        mcode_sql = "NULL" if legacy_mcode is None else str(legacy_mcode)

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

                {mcode_sql},

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

        """

        UPDATE menus

        SET label = 'Payment / Adjustment Entry',

            is_active = true,

            updated_at = now()

        WHERE code = 'adjustment_entry'

        """

    )

    op.execute(

        """

        UPDATE menus

        SET label = 'Contra Entry',

            is_active = true,

            updated_at = now()

        WHERE code = 'receipt_voucher_adjustment_entry'

        """

    )



    for code, _, _, _, _, _ in NEW_MENUS:

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



    for menu_code in ("adjustment_entry", "receipt_voucher_adjustment_entry"):

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

              AND m.code = '{menu_code}'

              AND NOT EXISTS (

                  SELECT 1 FROM role_menu_permissions rp

                  WHERE rp.role_id = r.id AND rp.menu_id = m.id

              )

            """

        )





def downgrade() -> None:

    codes = ", ".join(f"'{code}'" for code, *_ in NEW_MENUS)

    op.execute(f"DELETE FROM role_menu_permissions WHERE menu_id IN (SELECT id FROM menus WHERE code IN ({codes}))")

    op.execute(f"DELETE FROM menus WHERE code IN ({codes})")


