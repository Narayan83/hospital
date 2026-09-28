"""pathology result templates and menu

Revision ID: 042
Revises: 041
Create Date: 2026-06-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathology_result_templates",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("parameter_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("service_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parameter_id"], ["pathology_parameters.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["patient_service_masters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pathology_result_templates_code"),
        "pathology_result_templates",
        ["code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_pathology_result_templates_parameter_id"),
        "pathology_result_templates",
        ["parameter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pathology_result_templates_service_id"),
        "pathology_result_templates",
        ["service_id"],
        unique=False,
    )

    op.execute(
        """
        UPDATE menus SET sort_order = 8, updated_at = now()
        WHERE code = 'pathology_bill_reprint' AND sort_order < 8
        """
    )
    op.execute(
        """
        UPDATE menus SET sort_order = 7, updated_at = now()
        WHERE code = 'pathology_work_list' AND sort_order < 7
        """
    )
    op.execute(
        """
        UPDATE menus SET sort_order = 6, updated_at = now()
        WHERE code = 'pathology_bill' AND sort_order < 6
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
            'custom_template_creation',
            'Custom Template Creation',
            parent.id,
            5,
            154,
            'PTMPL',
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'pathology'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'custom_template_creation')
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
          AND m.code = 'custom_template_creation'
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
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'custom_template_creation')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'custom_template_creation'")
    op.execute(
        """
        UPDATE menus SET sort_order = 5, updated_at = now()
        WHERE code = 'pathology_bill'
        """
    )
    op.execute(
        """
        UPDATE menus SET sort_order = 6, updated_at = now()
        WHERE code = 'pathology_work_list'
        """
    )
    op.execute(
        """
        UPDATE menus SET sort_order = 7, updated_at = now()
        WHERE code = 'pathology_bill_reprint'
        """
    )
    op.drop_index(op.f("ix_pathology_result_templates_service_id"), table_name="pathology_result_templates")
    op.drop_index(op.f("ix_pathology_result_templates_parameter_id"), table_name="pathology_result_templates")
    op.drop_index(op.f("ix_pathology_result_templates_code"), table_name="pathology_result_templates")
    op.drop_table("pathology_result_templates")
