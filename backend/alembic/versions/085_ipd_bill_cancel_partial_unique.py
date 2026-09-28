"""Allow cancelling IPD bills by making admission unique only for active bills.

Revision ID: 085
Revises: 084
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "085"
down_revision: Union[str, None] = "084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_ipd_bill_per_admission", "ipd_bills", type_="unique")
    op.create_index(
        "uq_ipd_bill_per_admission_active",
        "ipd_bills",
        ["admission_id"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index("uq_ipd_bill_per_admission_active", table_name="ipd_bills")
    op.create_unique_constraint("uq_ipd_bill_per_admission", "ipd_bills", ["admission_id"])
