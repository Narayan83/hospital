"""patient number formats and sequences

Revision ID: 013
Revises: 012
Create Date: 2026-06-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_no_formats",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("pattern", sa.String(length=100), nullable=False),
        sa.Column("sample_output", sa.String(length=50), nullable=False),
        sa.Column("seq_pad_width", sa.Integer(), nullable=False),
        sa.Column("is_selected", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patient_no_formats_code"), "patient_no_formats", ["code"], unique=True)

    op.create_table(
        "number_sequences",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("scope_key", sa.String(length=80), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "scope_key", name="uq_number_sequences_scope"),
    )
    op.create_index(op.f("ix_number_sequences_entity_type"), "number_sequences", ["entity_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_number_sequences_entity_type"), table_name="number_sequences")
    op.drop_table("number_sequences")
    op.drop_index(op.f("ix_patient_no_formats_code"), table_name="patient_no_formats")
    op.drop_table("patient_no_formats")
