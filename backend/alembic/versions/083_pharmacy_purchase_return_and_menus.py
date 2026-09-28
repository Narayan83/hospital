"""Add pharmacy purchase bill_kind for returns; relocate medicine menus.

Revision ID: 083
Revises: 082
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "083"
down_revision: Union[str, None] = "082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pharmacy_purchase_bills",
        sa.Column("bill_kind", sa.String(length=20), server_default="purchase", nullable=False),
    )

    # Move medicine transaction menus under Medical Shop (bootstrap also syncs).
    op.execute(
        """
        UPDATE menus AS child
        SET parent_id = parent.id,
            is_active = true,
            updated_at = now()
        FROM menus AS parent
        WHERE parent.code = 'medical_shop'
          AND child.code IN (
              'medicine_indent',
              'medicine_purchase_return',
              'medicine_purchase_bill'
          )
        """
    )
    op.execute(
        """
        UPDATE menus
        SET is_active = false, updated_at = now()
        WHERE code = 'medicine_purchase_bill'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE menus AS child
        SET parent_id = parent.id,
            is_active = true,
            updated_at = now()
        FROM menus AS parent
        WHERE parent.code = 'transactions'
          AND child.code IN (
              'medicine_indent',
              'medicine_purchase_return',
              'medicine_purchase_bill'
          )
        """
    )
    op.drop_column("pharmacy_purchase_bills", "bill_kind")
