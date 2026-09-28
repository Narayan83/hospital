"""short bill master and transactions

Revision ID: 056
Revises: 055
Create Date: 2026-06-20

"""
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "056"
down_revision: Union[str, None] = "055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SHORT_BILL_TYPES = [
    ("SCAN", "Scan Bill", "scan_bill", "SCN", 1),
    ("XRAY", "XRay Bill", "xray_bill", "XRY", 2),
    ("OBS", "Observation Bill", "observation_bill", "OBS", 3),
    ("IMM", "Immunization Bill", "immunization_bill", "IMB", 4),
]


def upgrade() -> None:
    op.create_table(
        "short_bill_types",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("menu_code", sa.String(length=50), nullable=False),
        sa.Column("default_service_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("default_service_name", sa.String(length=200), nullable=True),
        sa.Column("default_rate", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("default_doctor_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("bill_prefix", sa.String(length=20), nullable=False, server_default="SB"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["default_doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["default_service_id"], ["patient_service_masters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("menu_code"),
    )
    op.create_index(op.f("ix_short_bill_types_code"), "short_bill_types", ["code"], unique=True)
    op.create_index(op.f("ix_short_bill_types_menu_code"), "short_bill_types", ["menu_code"], unique=True)

    op.create_table(
        "short_bills",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_no", sa.String(length=30), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("short_bill_type_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("patient_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("patient_name", sa.String(length=200), nullable=False),
        sa.Column("service_name", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.ForeignKeyConstraint(["short_bill_type_id"], ["short_bill_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bill_no"),
    )
    op.create_index(op.f("ix_short_bills_bill_no"), "short_bills", ["bill_no"], unique=True)
    op.create_index(op.f("ix_short_bills_short_bill_type_id"), "short_bills", ["short_bill_type_id"])
    op.create_index(op.f("ix_short_bills_patient_id"), "short_bills", ["patient_id"])
    op.create_index(op.f("ix_short_bills_created_by_user_id"), "short_bills", ["created_by_user_id"])

    conn = op.get_bind()
    for code, name, menu_code, prefix, sort_order in SHORT_BILL_TYPES:
        conn.execute(
            sa.text(
                """
                INSERT INTO short_bill_types
                (id, code, name, menu_code, bill_prefix, sort_order, is_active)
                VALUES (:id, :code, :name, :menu_code, :prefix, :sort_order, true)
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "id": str(uuid4()),
                "code": code,
                "name": name,
                "menu_code": menu_code,
                "prefix": prefix,
                "sort_order": sort_order,
            },
        )


def downgrade() -> None:
    op.drop_table("short_bills")
    op.drop_table("short_bill_types")
