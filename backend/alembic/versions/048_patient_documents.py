"""patient scanned documents and doctor view tracking

Revision ID: 048
Revises: 047
Create Date: 2026-06-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_documents",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("patient_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=True),
        sa.Column("document_type", sa.String(length=30), nullable=False, server_default="patient_document"),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scanner_name", sa.String(length=200), nullable=True),
        sa.Column("scanned_by_user_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["scanned_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patient_documents_patient_id"), "patient_documents", ["patient_id"], unique=False)
    op.create_index(op.f("ix_patient_documents_document_date"), "patient_documents", ["document_date"], unique=False)

    op.create_table(
        "patient_document_views",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("document_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["patient_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "doctor_id", name="uq_patient_document_view"),
    )
    op.create_index(
        op.f("ix_patient_document_views_doctor_id"), "patient_document_views", ["doctor_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_patient_document_views_doctor_id"), table_name="patient_document_views")
    op.drop_table("patient_document_views")
    op.drop_index(op.f("ix_patient_documents_document_date"), table_name="patient_documents")
    op.drop_index(op.f("ix_patient_documents_patient_id"), table_name="patient_documents")
    op.drop_table("patient_documents")
