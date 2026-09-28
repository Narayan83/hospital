"""opd tokens separate table

Revision ID: 024
Revises: 023
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opd_tokens",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("doctor_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("patient_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bill_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("token_number", sa.Integer(), nullable=False),
        sa.Column("token_date", sa.Date(), nullable=False),
        sa.Column("token_session", sa.String(length=10), nullable=False),
        sa.Column("visit_category", sa.String(length=20), nullable=False),
        sa.Column("bill_no", sa.String(length=30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bill_id"], ["opd_bills.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "doctor_id",
            "token_date",
            "token_session",
            "visit_category",
            "token_number",
            name="uq_opd_token_slot",
        ),
    )
    op.create_index(op.f("ix_opd_tokens_doctor_id"), "opd_tokens", ["doctor_id"], unique=False)
    op.create_index(op.f("ix_opd_tokens_patient_id"), "opd_tokens", ["patient_id"], unique=False)
    op.create_index(op.f("ix_opd_tokens_bill_id"), "opd_tokens", ["bill_id"], unique=False)
    op.create_index(op.f("ix_opd_tokens_token_date"), "opd_tokens", ["token_date"], unique=False)
    op.create_index(
        "ix_opd_tokens_lookup",
        "opd_tokens",
        ["doctor_id", "token_date", "token_session", "visit_category"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO opd_tokens (
            id, doctor_id, patient_id, bill_id, token_number, token_date,
            token_session, visit_category, bill_no, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            doctor_id,
            patient_id,
            id,
            token_number,
            CASE
                WHEN visit_category = 'appointment' AND appointment_date IS NOT NULL
                THEN appointment_date
                ELSE bill_date
            END,
            token_session,
            visit_category,
            bill_no,
            is_active,
            created_at,
            updated_at
        FROM opd_bills
        WHERE token_number IS NOT NULL
          AND doctor_id IS NOT NULL
          AND token_session IS NOT NULL
        """
    )

    op.drop_index("ix_opd_bills_doctor_token", table_name="opd_bills")
    op.drop_column("opd_bills", "token_session")
    op.drop_column("opd_bills", "token_number")


def downgrade() -> None:
    op.add_column("opd_bills", sa.Column("token_number", sa.Integer(), nullable=True))
    op.add_column("opd_bills", sa.Column("token_session", sa.String(length=10), nullable=True))

    op.execute(
        """
        UPDATE opd_bills b
        SET
            token_number = t.token_number,
            token_session = t.token_session
        FROM opd_tokens t
        WHERE t.bill_id = b.id AND t.is_active = true
        """
    )

    op.create_index(
        "ix_opd_bills_doctor_token",
        "opd_bills",
        ["doctor_id", "visit_category", "token_session", "appointment_date", "bill_date"],
        unique=False,
    )
    op.drop_index("ix_opd_tokens_lookup", table_name="opd_tokens")
    op.drop_index(op.f("ix_opd_tokens_token_date"), table_name="opd_tokens")
    op.drop_index(op.f("ix_opd_tokens_bill_id"), table_name="opd_tokens")
    op.drop_index(op.f("ix_opd_tokens_patient_id"), table_name="opd_tokens")
    op.drop_index(op.f("ix_opd_tokens_doctor_id"), table_name="opd_tokens")
    op.drop_table("opd_tokens")
