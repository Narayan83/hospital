"""patient aadhar scan path

Revision ID: 022
Revises: 021
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("aadhar_scan_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "aadhar_scan_path")
