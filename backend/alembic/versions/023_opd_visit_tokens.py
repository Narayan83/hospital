"""opd visit categories and doctor appointment token range

Revision ID: 023
Revises: 022
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "doctors",
        sa.Column("appointment_token_start", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "doctors",
        sa.Column("appointment_token_end", sa.Integer(), nullable=False, server_default="5"),
    )

    op.add_column(
        "opd_bills",
        sa.Column("visit_category", sa.String(length=20), nullable=False, server_default="opd"),
    )
    op.add_column("opd_bills", sa.Column("token_number", sa.Integer(), nullable=True))
    op.add_column("opd_bills", sa.Column("token_session", sa.String(length=10), nullable=True))
    op.add_column("opd_bills", sa.Column("appointment_date", sa.Date(), nullable=True))

    op.create_index(
        "ix_opd_bills_doctor_token",
        "opd_bills",
        ["doctor_id", "visit_category", "token_session", "appointment_date", "bill_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_opd_bills_doctor_token", table_name="opd_bills")
    op.drop_column("opd_bills", "appointment_date")
    op.drop_column("opd_bills", "token_session")
    op.drop_column("opd_bills", "token_number")
    op.drop_column("opd_bills", "visit_category")
    op.drop_column("doctors", "appointment_token_end")
    op.drop_column("doctors", "appointment_token_start")
