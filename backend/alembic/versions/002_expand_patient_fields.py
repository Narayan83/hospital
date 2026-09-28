"""expand patient fields for legacy form

Revision ID: 002
Revises: 001
Create Date: 2026-06-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("patients", "last_name", existing_type=sa.String(length=100), nullable=True)
    op.drop_column("patients", "address")

    op.add_column("patients", sa.Column("facility", sa.String(length=150), nullable=True))
    op.add_column("patients", sa.Column("title", sa.String(length=10), nullable=True))
    op.add_column("patients", sa.Column("middle_name", sa.String(length=100), nullable=True))
    op.add_column("patients", sa.Column("age", sa.Integer(), nullable=True))
    op.alter_column("patients", "blood_group", existing_type=sa.String(length=5), type_=sa.String(length=10), existing_nullable=True)

    op.add_column("patients", sa.Column("village_code", sa.String(length=20), nullable=True))
    op.add_column("patients", sa.Column("contact_address1", sa.String(length=200), nullable=True))
    op.add_column("patients", sa.Column("contact_address2", sa.String(length=200), nullable=True))
    op.add_column("patients", sa.Column("contact_address3", sa.String(length=200), nullable=True))
    op.add_column("patients", sa.Column("contact_address4", sa.String(length=200), nullable=True))
    op.add_column("patients", sa.Column("contact_address5", sa.String(length=20), nullable=True))

    op.add_column("patients", sa.Column("perm_address1", sa.String(length=200), nullable=True))
    op.add_column("patients", sa.Column("perm_address2", sa.String(length=200), nullable=True))
    op.add_column("patients", sa.Column("perm_address3", sa.String(length=200), nullable=True))
    op.add_column("patients", sa.Column("perm_address4", sa.String(length=200), nullable=True))
    op.add_column("patients", sa.Column("perm_address5", sa.String(length=20), nullable=True))

    op.add_column("patients", sa.Column("old_software_id", sa.String(length=50), nullable=True))
    op.add_column("patients", sa.Column("remarks", sa.Text(), nullable=True))
    op.add_column("patients", sa.Column("mobile", sa.String(length=20), nullable=True))
    op.add_column("patients", sa.Column("mobile2", sa.String(length=20), nullable=True))
    op.add_column("patients", sa.Column("scheme", sa.String(length=100), nullable=True))
    op.add_column("patients", sa.Column("aadhar_no", sa.String(length=20), nullable=True))
    op.add_column("patients", sa.Column("is_existing_patient", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("patients", sa.Column("patient_type", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "patient_type")
    op.drop_column("patients", "is_existing_patient")
    op.drop_column("patients", "aadhar_no")
    op.drop_column("patients", "scheme")
    op.drop_column("patients", "mobile2")
    op.drop_column("patients", "mobile")
    op.drop_column("patients", "remarks")
    op.drop_column("patients", "old_software_id")
    op.drop_column("patients", "perm_address5")
    op.drop_column("patients", "perm_address4")
    op.drop_column("patients", "perm_address3")
    op.drop_column("patients", "perm_address2")
    op.drop_column("patients", "perm_address1")
    op.drop_column("patients", "contact_address5")
    op.drop_column("patients", "contact_address4")
    op.drop_column("patients", "contact_address3")
    op.drop_column("patients", "contact_address2")
    op.drop_column("patients", "contact_address1")
    op.drop_column("patients", "village_code")
    op.drop_column("patients", "age")
    op.drop_column("patients", "middle_name")
    op.drop_column("patients", "title")
    op.drop_column("patients", "facility")
    op.add_column("patients", sa.Column("address", sa.Text(), nullable=True))
