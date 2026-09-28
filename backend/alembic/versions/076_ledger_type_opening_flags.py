"""ledger type, opening balance, cash/bank/deposit flags



Revision ID: 076

Revises: 075

Create Date: 2026-07-17



"""

from typing import Sequence, Union



import sqlalchemy as sa

from alembic import op



revision: str = "076"

down_revision: Union[str, None] = "075"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None



# code -> (ledger_type, is_cash, is_bank, is_patient_deposit)

LEDGER_META = [

    ("CASH", "ASSET", True, False, False),

    ("BANK-HDFC", "ASSET", False, True, False),

    ("BANK-ICICI", "ASSET", False, True, False),

    ("BANK-SBI", "ASSET", False, True, False),

    ("BANK-AXIS", "ASSET", False, True, False),

    ("OPD-RECEIPT", "INCOME", False, False, False),

    ("IPD-RECEIPT", "INCOME", False, False, False),

    ("PATHOLOGY", "INCOME", False, False, False),

    ("RADIOLOGY", "INCOME", False, False, False),

    ("PHARMACY", "INCOME", False, False, False),

    ("AMBULANCE", "INCOME", False, False, False),

    ("PAT-DEPOSIT", "LIABILITY", False, False, True),

    ("PATIENT-ACCOUNT", "LIABILITY", False, False, False),

    ("SALARY", "EXPENSE", False, False, False),

    ("MED-PURCHASE", "EXPENSE", False, False, False),

    ("LAB-EXPENSE", "EXPENSE", False, False, False),

    ("RENT", "EXPENSE", False, False, False),

    ("ELECTRICITY", "EXPENSE", False, False, False),

    ("EQUIPMENT", "ASSET", False, False, False),

    ("MAINTENANCE", "EXPENSE", False, False, False),

    ("INSURANCE", "ASSET", False, False, False),

]





def upgrade() -> None:

    op.add_column(

        "ledgers",

        sa.Column(

            "ledger_type",

            sa.String(length=20),

            nullable=False,

            server_default="ASSET",

        ),

    )

    op.add_column(

        "ledgers",

        sa.Column(

            "opening_balance",

            sa.Numeric(precision=14, scale=2),

            nullable=False,

            server_default="0",

        ),

    )

    op.add_column(

        "ledgers",

        sa.Column(

            "is_cash",

            sa.Boolean(),

            nullable=False,

            server_default=sa.text("false"),

        ),

    )

    op.add_column(

        "ledgers",

        sa.Column(

            "is_bank",

            sa.Boolean(),

            nullable=False,

            server_default=sa.text("false"),

        ),

    )

    op.add_column(

        "ledgers",

        sa.Column(

            "is_patient_deposit",

            sa.Boolean(),

            nullable=False,

            server_default=sa.text("false"),

        ),

    )

    op.create_index("ix_ledgers_ledger_type", "ledgers", ["ledger_type"])

    op.create_index("ix_ledgers_is_cash", "ledgers", ["is_cash"])

    op.create_index("ix_ledgers_is_bank", "ledgers", ["is_bank"])

    op.create_index("ix_ledgers_is_patient_deposit", "ledgers", ["is_patient_deposit"])



    for code, ledger_type, is_cash, is_bank, is_patient_deposit in LEDGER_META:

        op.execute(

            f"""

            UPDATE ledgers

            SET ledger_type = '{ledger_type}',

                is_cash = {'true' if is_cash else 'false'},

                is_bank = {'true' if is_bank else 'false'},

                is_patient_deposit = {'true' if is_patient_deposit else 'false'},

                updated_at = now()

            WHERE code = '{code}'

            """

        )



    op.execute(

        """

        UPDATE ledgers

        SET ledger_type = 'ASSET',

            is_bank = true,

            is_cash = false,

            updated_at = now()

        WHERE code LIKE 'BANK-%'

          AND is_bank = false

          AND is_cash = false

        """

    )





def downgrade() -> None:

    op.drop_index("ix_ledgers_is_patient_deposit", table_name="ledgers")

    op.drop_index("ix_ledgers_is_bank", table_name="ledgers")

    op.drop_index("ix_ledgers_is_cash", table_name="ledgers")

    op.drop_index("ix_ledgers_ledger_type", table_name="ledgers")

    op.drop_column("ledgers", "is_patient_deposit")

    op.drop_column("ledgers", "is_bank")

    op.drop_column("ledgers", "is_cash")

    op.drop_column("ledgers", "opening_balance")

    op.drop_column("ledgers", "ledger_type")


