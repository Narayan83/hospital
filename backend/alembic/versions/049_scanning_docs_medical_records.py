"""move scanning patient documents under medical records

Revision ID: 049
Revises: 048
Create Date: 2026-06-18

"""
from typing import Sequence, Union

from alembic import op

revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE menus AS child
        SET parent_id = parent.id,
            sort_order = 2
        FROM menus AS parent
        WHERE child.code = 'scanning_patient_documents'
          AND parent.code = 'medical_records'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE menus AS child
        SET parent_id = parent.id,
            sort_order = 2
        FROM menus AS parent
        WHERE child.code = 'scanning_patient_documents'
          AND parent.code = 'ward_management'
        """
    )
