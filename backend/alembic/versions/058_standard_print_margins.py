"""standard print margins and OPD bill paper size

Revision ID: 058
Revises: 057
Create Date: 2026-06-21

"""
from typing import Sequence, Union

from alembic import op

revision: str = "058"
down_revision: Union[str, None] = "057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE print_configs
        SET
            paper_size = 'A4',
            margin_top_mm = 8,
            margin_right_mm = 8,
            margin_bottom_mm = 10,
            margin_left_mm = 8,
            updated_at = now()
        WHERE code = 'OPD_BILL'
        """
    )
    op.execute(
        """
        UPDATE print_configs
        SET
            margin_top_mm = 8,
            margin_right_mm = 8,
            margin_bottom_mm = 10,
            margin_left_mm = 8,
            updated_at = now()
        WHERE code <> 'OPD_BILL'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE print_configs
        SET
            paper_size = 'A5',
            margin_top_mm = 12,
            margin_right_mm = 12,
            margin_bottom_mm = 15,
            margin_left_mm = 12,
            updated_at = now()
        WHERE code = 'OPD_BILL'
        """
    )
    op.execute(
        """
        UPDATE print_configs
        SET
            margin_top_mm = 12,
            margin_right_mm = 12,
            margin_bottom_mm = 15,
            margin_left_mm = 12,
            updated_at = now()
        WHERE code <> 'OPD_BILL'
        """
    )
