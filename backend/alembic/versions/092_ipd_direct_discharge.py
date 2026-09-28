"""Allow IPD discharge without an admission, and hide advance on the printed bill.

Revision ID: 092
Revises: 091
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "092"
down_revision: Union[str, None] = "091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("ipd_bills", "admission_id", existing_type=sa.UUID(as_uuid=False), nullable=True)
    op.add_column(
        "ipd_bills",
        sa.Column(
            "hide_advance_on_bill",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.execute("DELETE FROM ipd_bills WHERE admission_id IS NULL")
    op.drop_column("ipd_bills", "hide_advance_on_bill")
    op.alter_column("ipd_bills", "admission_id", existing_type=sa.UUID(as_uuid=False), nullable=False)
