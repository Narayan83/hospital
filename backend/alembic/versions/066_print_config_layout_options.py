"""print config layout_options for report-specific spacing

Revision ID: 066
Revises: 065
Create Date: 2026-06-26
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "066"
down_revision: Union[str, None] = "065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_PATHOLOGY_LAYOUT = {
    "font_size": 11,
    "row_padding": 5,
    "group_gap": 10,
    "sub_indent": 14,
}


def upgrade() -> None:
    op.add_column("print_configs", sa.Column("layout_options", JSONB, nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE print_configs
            SET layout_options = CAST(:layout AS jsonb)
            WHERE code = 'PATHOLOGY_REPORT' AND layout_options IS NULL
            """
        ).bindparams(layout=json.dumps(_DEFAULT_PATHOLOGY_LAYOUT))
    )


def downgrade() -> None:
    op.drop_column("print_configs", "layout_options")
