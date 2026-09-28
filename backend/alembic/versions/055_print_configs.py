"""print configs master for per-report printer and paper settings

Revision ID: 055
Revises: 054
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "055"
down_revision: Union[str, None] = "054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "print_configs",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("printer_name", sa.String(length=300), nullable=True),
        sa.Column("paper_size", sa.String(length=20), nullable=False),
        sa.Column("custom_width_mm", sa.Float(), nullable=True),
        sa.Column("custom_height_mm", sa.Float(), nullable=True),
        sa.Column("orientation", sa.String(length=20), nullable=False),
        sa.Column("print_mode", sa.String(length=20), nullable=False),
        sa.Column("margin_top_mm", sa.Float(), nullable=False),
        sa.Column("margin_right_mm", sa.Float(), nullable=False),
        sa.Column("margin_bottom_mm", sa.Float(), nullable=False),
        sa.Column("margin_left_mm", sa.Float(), nullable=False),
        sa.Column("copies", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_print_configs_code"), "print_configs", ["code"], unique=True)

    op.execute(
        """
        INSERT INTO print_configs (
            id, code, name, printer_name, paper_size, custom_width_mm, custom_height_mm,
            orientation, print_mode, margin_top_mm, margin_right_mm, margin_bottom_mm,
            margin_left_mm, copies, sort_order, is_active, created_at, updated_at
        )
        VALUES
        (
            gen_random_uuid(), 'OPD_BILL', 'OPD Bill / Receipt', NULL, 'A5', NULL, NULL,
            'portrait', 'direct', 12, 12, 15, 12, 1, 1, true, now(), now()
        ),
        (
            gen_random_uuid(), 'IPD_BILL', 'IPD Discharge Bill', NULL, 'A4', NULL, NULL,
            'portrait', 'preview', 12, 12, 15, 12, 1, 2, true, now(), now()
        ),
        (
            gen_random_uuid(), 'PATHOLOGY_BILL', 'Pathology Bill', NULL, 'A4', NULL, NULL,
            'portrait', 'preview', 12, 12, 15, 12, 1, 3, true, now(), now()
        ),
        (
            gen_random_uuid(), 'PATHOLOGY_REPORT', 'Pathology Lab Report', NULL, 'A4', NULL, NULL,
            'portrait', 'preview', 12, 12, 15, 12, 1, 4, true, now(), now()
        ),
        (
            gen_random_uuid(), 'DISCHARGE_SUMMARY', 'Discharge Summary', NULL, 'A4', NULL, NULL,
            'portrait', 'preview', 12, 12, 15, 12, 1, 5, true, now(), now()
        ),
        (
            gen_random_uuid(), 'OPD_CASESHEET', 'OPD Case Sheet', NULL, 'A4', NULL, NULL,
            'portrait', 'preview', 12, 12, 15, 12, 1, 6, true, now(), now()
        ),
        (
            gen_random_uuid(), 'PATIENT_CARD', 'Patient Card', NULL, 'A4', NULL, NULL,
            'portrait', 'preview', 12, 12, 15, 12, 1, 7, true, now(), now()
        ),
        (
            gen_random_uuid(), 'USER_CASH_REPORT', 'User Wise Cash Transaction Report', NULL, 'A4', NULL, NULL,
            'landscape', 'preview', 12, 12, 15, 12, 1, 8, true, now(), now()
        )
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
            'print_master',
            'Print Master',
            parent.id,
            39,
            NULL,
            'PRINTMSTR',
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'masters'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'print_master')
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
          AND m.code = 'print_master'
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
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'print_master')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'print_master'")
    op.drop_index(op.f("ix_print_configs_code"), table_name="print_configs")
    op.drop_table("print_configs")
