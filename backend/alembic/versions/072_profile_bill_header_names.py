"""add bill header names to hospital profile

Revision ID: 072
Revises: 071
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "072"
down_revision: Union[str, None] = "071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hospital_profile",
        sa.Column("pathology_name", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "hospital_profile",
        sa.Column("medical_shop_name", sa.String(length=200), nullable=True),
    )
    op.execute(
        """
        UPDATE hospital_profile
        SET
            pathology_name = COALESCE(NULLIF(pathology_name, ''), name || ' Pathology Lab'),
            medical_shop_name = COALESCE(NULLIF(medical_shop_name, ''), name || ' Medical Shop'),
            updated_at = now()
        WHERE code = 'MAIN'
        """
    )


def downgrade() -> None:
    op.drop_column("hospital_profile", "medical_shop_name")
    op.drop_column("hospital_profile", "pathology_name")
