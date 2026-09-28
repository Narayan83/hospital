"""pharmacy masters and sample medical shop records

Revision ID: 050
Revises: 049
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pharmacy_code_masters",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("master_type", sa.String(length=10), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_type", "code", name="uq_pharmacy_code_masters_type_code"),
    )
    op.create_index("ix_pharmacy_code_masters_master_type", "pharmacy_code_masters", ["master_type"])
    op.create_index("ix_pharmacy_code_masters_code", "pharmacy_code_masters", ["code"])

    op.create_table(
        "pharmacy_items",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("item_type", sa.String(length=10), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("generic_name", sa.String(length=200), nullable=True),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("mrp", sa.Numeric(12, 2), nullable=True),
        sa.Column("purchase_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("sale_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("manufacturer_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("schedule", sa.String(length=10), nullable=True),
        sa.Column("reorder_level", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["pharmacy_code_masters.id"]),
        sa.ForeignKeyConstraint(["manufacturer_id"], ["pharmacy_code_masters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_type", "code", name="uq_pharmacy_items_type_code"),
    )
    op.create_index("ix_pharmacy_items_item_type", "pharmacy_items", ["item_type"])
    op.create_index("ix_pharmacy_items_code", "pharmacy_items", ["code"])

    op.create_table(
        "pharmacy_suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("contact_person", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("gst_number", sa.String(length=20), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_pharmacy_suppliers_code", "pharmacy_suppliers", ["code"])

    op.create_table(
        "pharmacy_group_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["pharmacy_code_masters.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["pharmacy_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "item_id", name="uq_pharmacy_group_mappings"),
    )
    op.create_index("ix_pharmacy_group_mappings_group_id", "pharmacy_group_mappings", ["group_id"])
    op.create_index("ix_pharmacy_group_mappings_item_id", "pharmacy_group_mappings", ["item_id"])

    seeds = [
        ("MF", "CIPLA", "Cipla Ltd", 1),
        ("MF", "SUN", "Sun Pharmaceutical", 2),
        ("DC", "TAB", "Tablets", 1),
        ("DC", "SYR", "Syrups", 2),
        ("DC", "INJ", "Injections", 3),
        ("MG", "ANTIB", "Antibiotics", 1),
        ("MG", "ANALG", "Analgesics", 2),
        ("MK", "LOCAL", "Local Marketing", 1),
        ("DM", "MAIN", "Main Distributor", 1),
    ]
    for master_type, code, name, sort_order in seeds:
        op.execute(
            sa.text(
                """
                INSERT INTO pharmacy_code_masters (id, master_type, code, name, sort_order)
                SELECT gen_random_uuid(), :master_type, :code, :name, :sort_order
                WHERE NOT EXISTS (
                    SELECT 1 FROM pharmacy_code_masters
                    WHERE master_type = :master_type AND code = :code
                )
                """
            ).bindparams(
                master_type=master_type,
                code=code,
                name=name,
                sort_order=sort_order,
            )
        )


def downgrade() -> None:
    op.drop_table("pharmacy_group_mappings")
    op.drop_table("pharmacy_suppliers")
    op.drop_table("pharmacy_items")
    op.drop_table("pharmacy_code_masters")
