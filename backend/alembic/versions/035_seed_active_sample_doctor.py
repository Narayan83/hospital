"""ensure active sample doctor for OPD casesheet

Revision ID: 035
Revises: 034
Create Date: 2026-06-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO doctors (
            id,
            doctor_code,
            title,
            first_name,
            second_name,
            qualification,
            mobile,
            department_id,
            is_reference_doctor,
            is_existing,
            morning_token_start,
            evening_token_start,
            appointment_token_start,
            appointment_token_end,
            online_booking_token_start,
            online_booking_token_end,
            is_pathology_doctor,
            is_active,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            'SAMPLE',
            'Dr.',
            'Sample',
            'Doctor',
            'MBBS',
            '9999999999',
            dept.id,
            false,
            true,
            0,
            0,
            1,
            5,
            1,
            10,
            false,
            true,
            now(),
            now()
        FROM departments dept
        WHERE dept.code = 'GEN'
          AND NOT EXISTS (
              SELECT 1 FROM doctors existing WHERE existing.doctor_code = 'SAMPLE'
          )
        """
    )
    op.execute(
        """
        UPDATE doctors
        SET
            title = 'Dr.',
            first_name = 'Sample',
            second_name = 'Doctor',
            qualification = 'MBBS',
            mobile = '9999999999',
            department_id = (SELECT id FROM departments WHERE code = 'GEN' LIMIT 1),
            is_active = true,
            updated_at = now()
        WHERE doctor_code = 'SAMPLE'
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM doctors WHERE doctor_code = 'SAMPLE'")
