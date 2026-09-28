"""optional admission and include_admission_details flag

Revision ID: 047
Revises: 046
Create Date: 2026-06-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "047"
down_revision: Union[str, None] = "046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ipd_discharge_summaries",
        sa.Column("include_admission_details", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.alter_column("ipd_discharge_summaries", "admission_id", existing_type=sa.UUID(), nullable=True)
    op.execute(
        """
        UPDATE ipd_discharge_summaries
        SET include_admission_details = true
        WHERE admission_id IS NOT NULL
        """
    )
    op.alter_column("ipd_discharge_summaries", "include_admission_details", server_default=None)


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM ipd_discharge_summaries
        WHERE admission_id IS NULL
        """
    )
    op.alter_column("ipd_discharge_summaries", "admission_id", existing_type=sa.UUID(), nullable=False)
    op.drop_column("ipd_discharge_summaries", "include_admission_details")
