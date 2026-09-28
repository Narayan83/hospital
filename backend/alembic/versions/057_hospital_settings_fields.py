"""extend hospital profile with settings fields and dummy data

Revision ID: 057
Revises: 056
Create Date: 2026-06-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "057"
down_revision: Union[str, None] = "056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hospital_profile",
        sa.Column("address_line3", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "hospital_profile",
        sa.Column("address_line4", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "hospital_profile",
        sa.Column("gstin", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "hospital_profile",
        sa.Column("software_id", sa.String(length=50), nullable=True),
    )

    op.execute(
        """
        UPDATE hospital_profile
        SET
            name = 'City Care Hospital & Research Centre',
            address_line1 = '123 Medical Complex, 1st Floor',
            address_line2 = 'Near City General Hospital',
            address_line3 = 'MG Road, Central Business District',
            address_line4 = 'Bangalore, Karnataka',
            pin_code = '560001',
            phone = '080-12345678',
            email = 'info@citycarehospital.com',
            gstin = '29ABCDE1234F1Z5',
            software_id = 'HMS-2025-001',
            updated_at = now()
        WHERE code = 'MAIN'
        """
    )

    op.execute(
        """
        UPDATE menus
        SET label = 'Settings', updated_at = now()
        WHERE code = 'hospital_profile'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE menus
        SET label = 'Hospital Profile', updated_at = now()
        WHERE code = 'hospital_profile'
        """
    )
    op.drop_column("hospital_profile", "software_id")
    op.drop_column("hospital_profile", "gstin")
    op.drop_column("hospital_profile", "address_line4")
    op.drop_column("hospital_profile", "address_line3")
