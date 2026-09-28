"""Dashboard shortcuts table and setup menu.

Revision ID: 084
Revises: 083
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "084"
down_revision: Union[str, None] = "083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_shortcuts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("module_code", sa.String(length=100), nullable=False),
        sa.Column("button_label", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_dashboard_shortcuts_module_code", "dashboard_shortcuts", ["module_code"])

    # Seed default shortcuts
    op.execute(
        """
        INSERT INTO dashboard_shortcuts (
            id, module_code, button_label, description, sort_order, is_active, created_at, updated_at
        ) VALUES
        (gen_random_uuid(), 'opd_bill', 'OPD', 'Outpatient billing', 1, true, now(), now()),
        (gen_random_uuid(), 'ipd_bill', 'IPD', 'Inpatient billing', 2, true, now(), now()),
        (gen_random_uuid(), 'pathology_bill', 'Pathology', 'Pathology billing', 3, true, now(), now()),
        (gen_random_uuid(), 'doctor_wise_collection_report', 'Doctor Collection', 'Doctor wise collection report', 4, true, now(), now())
        """
    )

    op.execute(
        """
        INSERT INTO menus (
            id, code, label, parent_id, sort_order,
            legacy_mcode, legacy_form, parameters, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'dashboard_shortcut_setup',
            'Dashboard Shortcuts',
            parent.id,
            99,
            NULL,
            NULL,
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'masters'
          AND NOT EXISTS (
              SELECT 1 FROM menus WHERE code = 'dashboard_shortcut_setup'
          )
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
          AND m.code = 'dashboard_shortcut_setup'
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
        WHERE menu_id IN (
            SELECT id FROM menus WHERE code = 'dashboard_shortcut_setup'
        )
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'dashboard_shortcut_setup'")
    op.drop_index("ix_dashboard_shortcuts_module_code", table_name="dashboard_shortcuts")
    op.drop_table("dashboard_shortcuts")
