"""rbac auth tables

Revision ID: 003
Revises: 002
Create Date: 2026-06-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("role_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_role_name"), "roles", ["role_name"], unique=True)

    op.create_table(
        "menus",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=150), nullable=False),
        sa.Column("parent_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["menus.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_menus_code"), "menus", ["code"], unique=True)

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_column("users", "username")
    op.drop_column("users", "role")
    op.add_column("users", sa.Column("phone", sa.String(length=20), nullable=True))

    op.create_table(
        "user_role_mappings",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("role_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_role_mappings_role_id"), "user_role_mappings", ["role_id"])
    op.create_index(op.f("ix_user_role_mappings_user_id"), "user_role_mappings", ["user_id"])

    op.create_table(
        "role_menu_permissions",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("role_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("menu_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("can_view", sa.Boolean(), nullable=False),
        sa.Column("can_create", sa.Boolean(), nullable=False),
        sa.Column("can_update", sa.Boolean(), nullable=False),
        sa.Column("can_delete", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["menu_id"], ["menus.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "menu_id", name="uq_role_menu"),
    )
    op.create_index(op.f("ix_role_menu_permissions_menu_id"), "role_menu_permissions", ["menu_id"])
    op.create_index(op.f("ix_role_menu_permissions_role_id"), "role_menu_permissions", ["role_id"])

    op.create_table(
        "notification_setups",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("event_code", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_code", "user_id", name="uq_notification_user"),
    )
    op.create_index(op.f("ix_notification_setups_event_code"), "notification_setups", ["event_code"])
    op.create_index(op.f("ix_notification_setups_user_id"), "notification_setups", ["user_id"])


def downgrade() -> None:
    op.drop_table("notification_setups")
    op.drop_table("role_menu_permissions")
    op.drop_table("user_role_mappings")
    op.drop_column("users", "phone")
    op.add_column("users", sa.Column("role", sa.String(length=50), nullable=False, server_default="staff"))
    op.add_column("users", sa.Column("username", sa.String(length=50), nullable=False, server_default="user"))
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.drop_table("menus")
    op.drop_table("roles")
