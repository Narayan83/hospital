"""Track which user created each cashbook voucher (advance / payment / contra).

Revision ID: 091
Revises: 090
Create Date: 2026-09-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "091"
down_revision: Union[str, None] = "090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cashbook_vouchers",
        sa.Column("created_by_user_id", UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        "fk_cashbook_vouchers_created_by_user_id_users",
        "cashbook_vouchers",
        "users",
        ["created_by_user_id"],
        ["id"],
    )
    op.create_index(
        "ix_cashbook_vouchers_created_by_user_id",
        "cashbook_vouchers",
        ["created_by_user_id"],
    )

    # Bill vouchers already know their user through the source bill — backfill them
    # so the user wise cash report lines up with historical data.
    for source_type, table in (
        ("opd_bill", "opd_bills"),
        ("ipd_bill", "ipd_bills"),
    ):
        op.execute(
            f"""
            UPDATE cashbook_vouchers v
            SET created_by_user_id = b.created_by_user_id
            FROM {table} b
            WHERE v.source_id = b.id
              AND v.source_type = '{source_type}'
              AND v.created_by_user_id IS NULL
              AND b.created_by_user_id IS NOT NULL
            """
        )


def downgrade() -> None:
    op.drop_index("ix_cashbook_vouchers_created_by_user_id", table_name="cashbook_vouchers")
    op.drop_constraint(
        "fk_cashbook_vouchers_created_by_user_id_users",
        "cashbook_vouchers",
        type_="foreignkey",
    )
    op.drop_column("cashbook_vouchers", "created_by_user_id")
