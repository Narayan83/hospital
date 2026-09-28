"""seed sample ledgers

Revision ID: 032
Revises: 031
Create Date: 2026-06-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SAMPLE_LEDGERS = [
    ("CASH", "Cash Account", 1),
    ("BANK-HDFC", "HDFC Bank - Current Account", 2),
    ("BANK-ICICI", "ICICI Bank - Current Account", 3),
    ("BANK-SBI", "State Bank of India - Savings Account", 4),
    ("BANK-AXIS", "Axis Bank - Current Account", 5),
    ("OPD-RECEIPT", "OPD Receipts", 10),
    ("IPD-RECEIPT", "IPD Receipts", 11),
    ("PATHOLOGY", "Pathology Income", 12),
    ("RADIOLOGY", "Radiology / Scan Income", 13),
    ("PHARMACY", "Pharmacy Sales", 14),
    ("AMBULANCE", "Ambulance Service Income", 15),
    ("PAT-DEPOSIT", "Patient Security Deposit", 16),
    ("SALARY", "Staff Salary Expense", 20),
    ("MED-PURCHASE", "Medicine Purchase", 21),
    ("LAB-EXPENSE", "Laboratory Consumables", 22),
    ("RENT", "Hospital Rent Expense", 23),
    ("ELECTRICITY", "Electricity Expense", 24),
    ("EQUIPMENT", "Medical Equipment", 25),
    ("MAINTENANCE", "Building & Equipment Maintenance", 26),
    ("INSURANCE", "Insurance Claims Receivable", 27),
]


def upgrade() -> None:
    values_sql = ",\n            ".join(
        f"(gen_random_uuid(), '{code}', '{name}', {sort_order}, true, now(), now())"
        for code, name, sort_order in SAMPLE_LEDGERS
    )
    op.execute(
        f"""
        INSERT INTO ledgers (
            id, code, name, sort_order, is_active, created_at, updated_at
        )
        SELECT v.id, v.code, v.name, v.sort_order, v.is_active, v.created_at, v.updated_at
        FROM (VALUES
            {values_sql}
        ) AS v(id, code, name, sort_order, is_active, created_at, updated_at)
        WHERE NOT EXISTS (
            SELECT 1 FROM ledgers existing WHERE existing.code = v.code
        )
        """
    )


def downgrade() -> None:
    codes = ", ".join(f"'{code}'" for code, _, _ in SAMPLE_LEDGERS)
    op.execute(f"DELETE FROM ledgers WHERE code IN ({codes})")
