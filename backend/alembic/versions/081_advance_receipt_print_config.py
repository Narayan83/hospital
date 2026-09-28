"""Seed advance receipt print config.

Revision ID: 081
Revises: 080
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op

revision: str = "081"
down_revision: Union[str, None] = "080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO print_configs (
            id, code, name, printer_name, paper_size, custom_width_mm, custom_height_mm,
            orientation, print_mode, margin_top_mm, margin_right_mm, margin_bottom_mm,
            margin_left_mm, copies, sort_order, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'ADVANCE_RECEIPT',
            'Advance Receipt',
            NULL,
            'A5',
            NULL,
            NULL,
            'portrait',
            'direct',
            12, 12, 15, 12,
            1,
            20,
            true,
            now(),
            now()
        WHERE NOT EXISTS (
            SELECT 1 FROM print_configs WHERE code = 'ADVANCE_RECEIPT'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM print_configs WHERE code = 'ADVANCE_RECEIPT'")
