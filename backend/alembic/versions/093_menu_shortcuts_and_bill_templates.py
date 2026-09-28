"""Per-screen menu shortcuts and bill template designer menu.

Revision ID: 093
Revises: 092
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "093"
down_revision: Union[str, None] = "092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dashboard_shortcuts",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.add_column(
        "dashboard_shortcuts",
        sa.Column("host_code", sa.String(length=100), nullable=False, server_default="dashboard"),
    )
    op.create_foreign_key(
        "fk_dashboard_shortcuts_user_id",
        "dashboard_shortcuts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_dashboard_shortcuts_user_id", "dashboard_shortcuts", ["user_id"])
    op.create_index("ix_dashboard_shortcuts_host_code", "dashboard_shortcuts", ["host_code"])

    op.execute(
        """
        UPDATE menus
        SET label = 'Menu Shortcuts'
        WHERE code = 'dashboard_shortcut_setup'
        """
    )

    op.execute(
        """
        INSERT INTO print_configs (
            id, code, name, printer_name, paper_size, custom_width_mm, custom_height_mm,
            orientation, print_mode, margin_top_mm, margin_right_mm, margin_bottom_mm,
            margin_left_mm, copies, sort_order, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), 'PHARMACY_SALE_BILL', 'Pharmacy Sale Bill', NULL, 'A5', NULL, NULL,
            'portrait', 'preview', 12, 12, 15, 12, 1, 20, true, now(), now()
        WHERE NOT EXISTS (SELECT 1 FROM print_configs WHERE code = 'PHARMACY_SALE_BILL')
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
            'print_template_designer',
            'Bill Template Designer',
            parent.id,
            40,
            NULL,
            NULL,
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'masters'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'print_template_designer')
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
        WHERE m.code = 'print_template_designer'
          AND (
              r.role_name = 'Super Admin'
              OR EXISTS (
                  SELECT 1
                  FROM role_menu_permissions rp
                  JOIN menus pm ON pm.id = rp.menu_id
                  WHERE rp.role_id = r.id
                    AND pm.code = 'print_master'
                    AND rp.can_view = true
              )
          )
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
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'print_template_designer')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'print_template_designer'")
    op.execute("DELETE FROM print_configs WHERE code = 'PHARMACY_SALE_BILL'")
    op.execute(
        """
        UPDATE menus SET label = 'Dashboard Shortcuts' WHERE code = 'dashboard_shortcut_setup'
        """
    )
    op.drop_index("ix_dashboard_shortcuts_host_code", table_name="dashboard_shortcuts")
    op.drop_index("ix_dashboard_shortcuts_user_id", table_name="dashboard_shortcuts")
    op.drop_constraint("fk_dashboard_shortcuts_user_id", "dashboard_shortcuts", type_="foreignkey")
    op.drop_column("dashboard_shortcuts", "host_code")
    op.drop_column("dashboard_shortcuts", "user_id")
