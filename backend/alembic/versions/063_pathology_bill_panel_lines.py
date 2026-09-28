"""pathology bill panel line fields

Revision ID: 063
Revises: 062
Create Date: 2026-06-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "063"
down_revision: Union[str, None] = "062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pathology_bill_lines",
        sa.Column("panel_service_id", sa.UUID(as_uuid=False), nullable=True),
    )
    op.add_column(
        "pathology_bill_lines",
        sa.Column("panel_name", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "pathology_bill_lines",
        sa.Column("reference_range_text", sa.String(length=250), nullable=True),
    )
    op.create_foreign_key(
        "fk_pathology_bill_lines_panel_service",
        "pathology_bill_lines",
        "patient_service_masters",
        ["panel_service_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_pathology_bill_lines_panel_service",
        "pathology_bill_lines",
        type_="foreignkey",
    )
    op.drop_column("pathology_bill_lines", "reference_range_text")
    op.drop_column("pathology_bill_lines", "panel_name")
    op.drop_column("pathology_bill_lines", "panel_service_id")
