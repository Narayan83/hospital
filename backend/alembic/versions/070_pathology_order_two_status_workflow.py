"""simplify pathology order workflow to two statuses (billed, report_ready)

Revision ID: 070
Revises: 069
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "070"
down_revision: Union[str, None] = "069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLLAPSE = {
    "sample_collected": "billed",
    "in_process": "billed",
    "delivered": "report_ready",
}


def upgrade() -> None:
    orders = sa.table("pathology_orders", sa.column("status", sa.String))
    for old_status, new_status in _COLLAPSE.items():
        op.execute(
            orders.update()
            .where(orders.c.status == old_status)
            .values(status=new_status)
        )
    op.drop_column("pathology_orders", "delivered_at")


def downgrade() -> None:
    op.add_column(
        "pathology_orders",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
