"""Bump Pathology Report default font size in print_configs.

Revision ID: 088
Revises: 087
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op

revision: str = "088"
down_revision: Union[str, None] = "087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Raise compact defaults that were reduced for page fit; customer wants larger text.
    op.execute(
        """
        UPDATE print_configs
        SET layout_options = COALESCE(layout_options, '{}'::jsonb)
            || '{"font_size": 13, "row_padding": 6, "group_gap": 12, "sub_indent": 14}'::jsonb,
            updated_at = now()
        WHERE code = 'PATHOLOGY_REPORT'
          AND (
            layout_options IS NULL
            OR COALESCE((layout_options->>'font_size')::int, 0) <= 11
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE print_configs
        SET layout_options = COALESCE(layout_options, '{}'::jsonb)
            || '{"font_size": 11, "row_padding": 5, "group_gap": 10, "sub_indent": 14}'::jsonb,
            updated_at = now()
        WHERE code = 'PATHOLOGY_REPORT'
        """
    )
