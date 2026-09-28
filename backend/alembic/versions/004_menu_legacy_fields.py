"""menu legacy reference fields

Revision ID: 004
Revises: 003
Create Date: 2026-06-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("menus", sa.Column("legacy_mcode", sa.Integer(), nullable=True))
    op.add_column("menus", sa.Column("legacy_form", sa.String(length=80), nullable=True))
    op.add_column("menus", sa.Column("parameters", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("menus", "parameters")
    op.drop_column("menus", "legacy_form")
    op.drop_column("menus", "legacy_mcode")
