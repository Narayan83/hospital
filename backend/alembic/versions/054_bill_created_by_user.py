"""bill created_by_user_id for user-wise cash reports

Revision ID: 054
Revises: 053
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "054"
down_revision: Union[str, None] = "053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_created_by(table: str) -> None:
    op.add_column(
        table,
        sa.Column("created_by_user_id", sa.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        f"fk_{table}_created_by_user_id_users",
        table,
        "users",
        ["created_by_user_id"],
        ["id"],
    )
    op.create_index(
        op.f(f"ix_{table}_created_by_user_id"),
        table,
        ["created_by_user_id"],
        unique=False,
    )


def upgrade() -> None:
    for table in ("opd_bills", "ipd_bills", "pathology_bills"):
        _add_created_by(table)

    op.execute(
        """
        UPDATE opd_bills
        SET created_by_user_id = u.id
        FROM users u
        WHERE opd_bills.created_by_user_id IS NULL
          AND u.email = 'admin@admin.com'
        """
    )
    op.execute(
        """
        UPDATE ipd_bills
        SET created_by_user_id = u.id
        FROM users u
        WHERE ipd_bills.created_by_user_id IS NULL
          AND u.email = 'admin@admin.com'
        """
    )
    op.execute(
        """
        UPDATE pathology_bills
        SET created_by_user_id = u.id
        FROM users u
        WHERE pathology_bills.created_by_user_id IS NULL
          AND u.email = 'admin@admin.com'
        """
    )


def downgrade() -> None:
    for table in ("pathology_bills", "ipd_bills", "opd_bills"):
        op.drop_index(op.f(f"ix_{table}_created_by_user_id"), table_name=table)
        op.drop_constraint(f"fk_{table}_created_by_user_id_users", table, type_="foreignkey")
        op.drop_column(table, "created_by_user_id")
