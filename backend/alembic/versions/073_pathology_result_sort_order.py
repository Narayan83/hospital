"""pathology results sort_order for stable display/print order

Revision ID: 073
Revises: 072
Create Date: 2026-07-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "073"
down_revision: Union[str, None] = "072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pathology_results",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    # Backfill from bill-line order so existing work-list / reports stay consistent.
    op.execute(
        """
        UPDATE pathology_results AS pr
        SET sort_order = sub.rn
        FROM (
            SELECT
                pr2.id,
                (ROW_NUMBER() OVER (
                    PARTITION BY pr2.order_id
                    ORDER BY COALESCE(pbl.sort_order, 999999), pr2.created_at, pr2.id
                ) - 1) AS rn
            FROM pathology_results AS pr2
            LEFT JOIN pathology_bill_lines AS pbl ON pbl.id = pr2.bill_line_id
        ) AS sub
        WHERE pr.id = sub.id
        """
    )
    op.alter_column("pathology_results", "sort_order", server_default=None)


def downgrade() -> None:
    op.drop_column("pathology_results", "sort_order")
