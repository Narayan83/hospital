"""rename diagnose management menu to discharge summary

Revision ID: 045
Revises: 044
Create Date: 2026-06-16

"""
from typing import Sequence, Union

from alembic import op

revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE menus
        SET label = 'Discharge Summary', updated_at = now()
        WHERE code = 'diagnose_management'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE menus
        SET label = 'Diagnose Management', updated_at = now()
        WHERE code = 'diagnose_management'
        """
    )
