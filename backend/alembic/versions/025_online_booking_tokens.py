"""doctor online booking token range

Revision ID: 025
Revises: 024
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "doctors",
        sa.Column("online_booking_token_start", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "doctors",
        sa.Column("online_booking_token_end", sa.Integer(), nullable=False, server_default="10"),
    )


def downgrade() -> None:
    op.drop_column("doctors", "online_booking_token_end")
    op.drop_column("doctors", "online_booking_token_start")
