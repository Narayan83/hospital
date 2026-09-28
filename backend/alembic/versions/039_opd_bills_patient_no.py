"""store readable patient_no on opd_bills

Revision ID: 039
Revises: 038
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("opd_bills", sa.Column("patient_no", sa.String(length=20), nullable=True))
    op.execute(
        """
        UPDATE opd_bills AS b
        SET patient_no = p.patient_no
        FROM patients AS p
        WHERE b.patient_id = p.id
          AND b.patient_no IS NULL
        """
    )
    op.execute(
        """
        UPDATE opd_bills
        SET patient_no = 'UNKNOWN'
        WHERE patient_no IS NULL
        """
    )
    op.alter_column("opd_bills", "patient_no", nullable=False)
    op.create_index(op.f("ix_opd_bills_patient_no"), "opd_bills", ["patient_no"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_opd_bills_patient_no"), table_name="opd_bills")
    op.drop_column("opd_bills", "patient_no")
