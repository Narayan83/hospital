"""pathology bill line result + abnormal flag

Revision ID: 067
Revises: 066
Create Date: 2026-06-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "067"
down_revision: Union[str, None] = "066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pathology_bill_lines",
        sa.Column("result_value", sa.String(length=250), nullable=True),
    )
    op.add_column(
        "pathology_bill_lines",
        sa.Column(
            "is_abnormal",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("pathology_bill_lines", "is_abnormal")
    op.drop_column("pathology_bill_lines", "result_value")
