"""hospital sections, prefixes, patient section link

Revision ID: 010
Revises: 009
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hospital_sections",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hospital_sections_code"), "hospital_sections", ["code"], unique=True)

    op.create_table(
        "prefixes",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("prefix_value", sa.String(length=20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prefixes_code"), "prefixes", ["code"], unique=True)

    op.add_column("patients", sa.Column("hospital_section_id", sa.UUID(as_uuid=False), nullable=True))
    op.create_foreign_key(
        "fk_patients_hospital_section_id",
        "patients",
        "hospital_sections",
        ["hospital_section_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_patients_hospital_section_id", "patients", type_="foreignkey")
    op.drop_column("patients", "hospital_section_id")
    op.drop_index(op.f("ix_prefixes_code"), table_name="prefixes")
    op.drop_table("prefixes")
    op.drop_index(op.f("ix_hospital_sections_code"), table_name="hospital_sections")
    op.drop_table("hospital_sections")
