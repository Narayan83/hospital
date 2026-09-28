"""seed sample discharge summary for testing reprint

Revision ID: 046
Revises: 045
Create Date: 2026-06-16

"""
from typing import Sequence, Union

from alembic import op

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO ipd_discharge_summaries (
            id,
            summary_no,
            summary_date,
            admission_id,
            patient_id,
            doctor_id,
            chief_complaint,
            history_of_illness,
            diagnosis_on_admission,
            final_diagnosis,
            investigation,
            treatment_given,
            procedures,
            condition_on_discharge,
            medications_on_discharge,
            advice_follow_up,
            remarks,
            is_active,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            'DS202600001',
            COALESCE(a.discharge_date, CURRENT_DATE),
            a.id,
            a.patient_id,
            a.doctor_id,
            'Pain abdomen',
            'H/O Amenorrhea - 9 Months.
C/o Pain abdomen - 6 hours.',
            COALESCE(a.diagnosis, 'Antenatal case'),
            'P2L2 with FTND of Female baby',
            'HB: 12.5
HIV: NON REACTIVE
HBsAg: NEGATIVE
WBC Count: 4400
Platelet Count: 2.16
RBS: 130
HBA1C: 5.2
VDRL: NEGATIVE',
            'P2L2 with FTND of Female baby at term',
            'Normal vaginal delivery',
            'Stable',
            'T. AZPAR SP 1-0-1
T. CEFAMID O 1-0-1
T. PAN D 1-0-1',
            'Review after 7 days. Adequate rest and hydration.',
            'Sample discharge summary for testing reprint.',
            true,
            now(),
            now()
        FROM ipd_admissions a
        WHERE a.status = 'discharged'
          AND a.is_active = true
          AND NOT EXISTS (
              SELECT 1 FROM ipd_discharge_summaries existing
              WHERE existing.admission_id = a.id
          )
        ORDER BY a.discharge_date DESC NULLS LAST, a.created_at DESC
        LIMIT 1
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM ipd_discharge_summaries
        WHERE summary_no = 'DS202600001'
          AND remarks = 'Sample discharge summary for testing reprint.'
        """
    )
