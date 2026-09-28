"""service notes master + menu

Revision ID: 068
Revises: 067
Create Date: 2026-06-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "068"
down_revision: Union[str, None] = "067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "service_notes",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("service_code", sa.String(length=30), nullable=True),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_service_notes_service_code"),
        "service_notes",
        ["service_code"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO menus (
            id, code, label, parent_id, sort_order,
            legacy_mcode, legacy_form, parameters, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'pathology_notes_master',
            'Notes Master',
            parent.id,
            9,
            NULL,
            NULL,
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'pathology'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'pathology_notes_master')
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
          AND m.code = 'pathology_notes_master'
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
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'pathology_notes_master')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'pathology_notes_master'")
    op.drop_index(op.f("ix_service_notes_service_code"), table_name="service_notes")
    op.drop_table("service_notes")
