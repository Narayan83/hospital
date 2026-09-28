"""backfill doctor and token on existing OPD bills missing them

Revision ID: 059
Revises: 058
Create Date: 2026-06-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "059"
down_revision: Union[str, None] = "058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        WITH default_doctor AS (
            SELECT id, department_id
            FROM doctors
            WHERE is_active = true
            ORDER BY doctor_code
            LIMIT 1
        )
        UPDATE opd_bills AS bill
        SET
            doctor_id = doctor.id,
            department_id = COALESCE(bill.department_id, doctor.department_id),
            updated_at = now()
        FROM default_doctor AS doctor
        WHERE bill.doctor_id IS NULL
          AND bill.is_active = true
        """
    )

    op.execute(
        """
        INSERT INTO opd_tokens (
            id,
            doctor_id,
            patient_id,
            bill_id,
            bill_no,
            token_number,
            token_date,
            token_session,
            visit_category,
            is_active,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            bill.doctor_id,
            bill.patient_id,
            bill.id,
            bill.bill_no,
            COALESCE(
                (
                    SELECT COUNT(*)
                    FROM opd_tokens existing
                    WHERE existing.is_active = true
                      AND existing.doctor_id = bill.doctor_id
                      AND existing.token_date = CASE
                            WHEN bill.visit_category IN ('appointment', 'online_booking')
                                AND bill.appointment_date IS NOT NULL
                            THEN bill.appointment_date
                            ELSE bill.bill_date
                        END
                      AND existing.token_session = 'morning'
                      AND existing.visit_category = bill.visit_category
                ),
                0
            ) + ROW_NUMBER() OVER (
                PARTITION BY
                    bill.doctor_id,
                    CASE
                        WHEN bill.visit_category IN ('appointment', 'online_booking')
                            AND bill.appointment_date IS NOT NULL
                        THEN bill.appointment_date
                        ELSE bill.bill_date
                    END,
                    bill.visit_category
                ORDER BY bill.bill_date, bill.created_at, bill.bill_no
            ),
            CASE
                WHEN bill.visit_category IN ('appointment', 'online_booking')
                    AND bill.appointment_date IS NOT NULL
                THEN bill.appointment_date
                ELSE bill.bill_date
            END,
            'morning',
            bill.visit_category,
            true,
            now(),
            now()
        FROM opd_bills bill
        WHERE bill.is_active = true
          AND bill.doctor_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM opd_tokens token
              WHERE token.bill_id = bill.id
                AND token.is_active = true
          )
        """
    )


def downgrade() -> None:
    pass
