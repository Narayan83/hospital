"""pathology order workflow status (billed/sample_collected/in_process/report_ready/delivered)

Revision ID: 069
Revises: 068
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "069"
down_revision: Union[str, None] = "068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RENAMES = {
    "ordered": "billed",
    "processing": "in_process",
    "completed": "in_process",
    "authorized": "report_ready",
}


def upgrade() -> None:
    op.add_column(
        "pathology_orders",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    orders = sa.table("pathology_orders", sa.column("status", sa.String))
    for old_status, new_status in _RENAMES.items():
        op.execute(
            orders.update()
            .where(orders.c.status == old_status)
            .values(status=new_status)
        )


def downgrade() -> None:
    orders = sa.table("pathology_orders", sa.column("status", sa.String))
    reverse = {
        "billed": "ordered",
        "sample_collected": "ordered",
        "in_process": "processing",
        "report_ready": "authorized",
        "delivered": "authorized",
    }
    for new_status, old_status in reverse.items():
        op.execute(
            orders.update()
            .where(orders.c.status == new_status)
            .values(status=old_status)
        )
    op.drop_column("pathology_orders", "delivered_at")
