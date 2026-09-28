"""bill line doctor sharing amounts and doctor collection report menu

Revision ID: 074
Revises: 073
Create Date: 2026-07-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "074"
down_revision: Union[str, None] = "073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_sharing_columns(table: str) -> None:
    op.add_column(
        table,
        sa.Column("original_rate", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        table,
        sa.Column("hospital_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        table,
        sa.Column("doctor_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        table,
        sa.Column(
            "sharing_doctor_id",
            sa.UUID(as_uuid=False),
            sa.ForeignKey("doctors.id"),
            nullable=True,
        ),
    )
    op.create_index(
        op.f(f"ix_{table}_sharing_doctor_id"),
        table,
        ["sharing_doctor_id"],
        unique=False,
    )


def upgrade() -> None:
    _add_sharing_columns("opd_bill_lines")
    _add_sharing_columns("ipd_bill_lines")
    op.alter_column("opd_bill_lines", "hospital_amount", server_default=None)
    op.alter_column("opd_bill_lines", "doctor_amount", server_default=None)
    op.alter_column("ipd_bill_lines", "hospital_amount", server_default=None)
    op.alter_column("ipd_bill_lines", "doctor_amount", server_default=None)

    op.execute(
        """
        INSERT INTO menus (
            id, code, label, parent_id, sort_order,
            legacy_mcode, legacy_form, parameters, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'doctor_wise_collection_report',
            'Doctor wise Collection Report',
            parent.id,
            28,
            6,
            'ALLUREP',
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'reports'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'doctor_wise_collection_report')
        """
    )

    op.execute(
        """
        INSERT INTO role_menu_permissions (
            id, role_id, menu_id, can_view, can_create, can_update, can_delete,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            r.id,
            m.id,
            true, true, true, true,
            now(), now()
        FROM roles r
        CROSS JOIN menus m
        WHERE r.role_name = 'Super Admin'
          AND m.code = 'doctor_wise_collection_report'
          AND NOT EXISTS (
              SELECT 1 FROM role_menu_permissions rp
              WHERE rp.role_id = r.id AND rp.menu_id = m.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_menu_permissions
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'doctor_wise_collection_report')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'doctor_wise_collection_report'")

    for table in ("ipd_bill_lines", "opd_bill_lines"):
        op.drop_index(op.f(f"ix_{table}_sharing_doctor_id"), table_name=table)
        op.drop_column(table, "sharing_doctor_id")
        op.drop_column(table, "doctor_amount")
        op.drop_column(table, "hospital_amount")
        op.drop_column(table, "original_rate")
