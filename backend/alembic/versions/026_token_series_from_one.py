"""normalize token series to start from 1

Revision ID: 026
Revises: 025
Create Date: 2026-06-12

"""
from typing import Sequence, Union

from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE doctors
        SET
            morning_token_start = 1,
            evening_token_start = 1,
            appointment_token_start = 1,
            online_booking_token_start = 1
        """
    )


def downgrade() -> None:
    pass
