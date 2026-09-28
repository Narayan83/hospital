"""discharge summary admission and discharge dates

Revision ID: 061
Revises: 060
Create Date: 2026-06-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "061"
down_revision: Union[str, None] = "060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ipd_discharge_summaries", sa.Column("admission_date", sa.Date(), nullable=True))
    op.add_column("ipd_discharge_summaries", sa.Column("discharge_date", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE ipd_discharge_summaries ds
        SET admission_date = a.admission_date,
            discharge_date = COALESCE(a.discharge_date, ds.summary_date)
        FROM ipd_admissions a
        WHERE ds.admission_id = a.id
          AND ds.admission_date IS NULL
        """
    )
    op.execute(
        """
        UPDATE ipd_discharge_summaries
        SET admission_date = summary_date,
            discharge_date = summary_date
        WHERE admission_date IS NULL
        """
    )
    op.alter_column("ipd_discharge_summaries", "admission_date", nullable=False)
    op.alter_column("ipd_discharge_summaries", "discharge_date", nullable=False)


def downgrade() -> None:
    op.drop_column("ipd_discharge_summaries", "discharge_date")
    op.drop_column("ipd_discharge_summaries", "admission_date")
