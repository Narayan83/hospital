"""Advance receipt: require print preview and ensure print config.

Revision ID: 086
Revises: 085
Create Date: 2026-07-22
"""

from typing import Sequence, Union

from alembic import op

revision: str = "086"
down_revision: Union[str, None] = "085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure Advance Receipt exists in Print Setup (Masters → Print Master).
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
            'preview',
            10, 10, 12, 10,
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
    # Existing installs were seeded as direct print — switch to preview.
    op.execute(
        """
        UPDATE print_configs
        SET print_mode = 'preview',
            name = COALESCE(NULLIF(TRIM(name), ''), 'Advance Receipt'),
            paper_size = COALESCE(paper_size, 'A5'),
            orientation = COALESCE(orientation, 'portrait'),
            updated_at = now()
        WHERE code = 'ADVANCE_RECEIPT'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE print_configs
        SET print_mode = 'direct',
            updated_at = now()
        WHERE code = 'ADVANCE_RECEIPT'
        """
    )
