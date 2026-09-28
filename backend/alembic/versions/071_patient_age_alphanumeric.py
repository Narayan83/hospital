"""change patients.age from integer to free-text (e.g. '8 Months', '45 Days')

Revision ID: 071
Revises: 070
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "071"
down_revision: Union[str, None] = "070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "patients",
        "age",
        existing_type=sa.Integer(),
        type_=sa.String(length=20),
        existing_nullable=True,
        postgresql_using="age::varchar(20)",
    )


def downgrade() -> None:
    op.alter_column(
        "patients",
        "age",
        existing_type=sa.String(length=20),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="NULLIF(regexp_replace(age, '[^0-9]', '', 'g'), '')::integer",
    )
