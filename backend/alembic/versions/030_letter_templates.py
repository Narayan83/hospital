"""letter templates master

Revision ID: 030
Revises: 029
Create Date: 2026-06-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "letter_templates",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_letter_templates_code"), "letter_templates", ["code"], unique=True)

    op.execute(
        """
        INSERT INTO letter_templates (
            id, code, name, subject, body, sort_order, is_active, created_at, updated_at
        )
        VALUES
        (
            gen_random_uuid(),
            'DISCHARGE',
            'Discharge Summary Letter',
            'Discharge Summary - {{patient_name}}',
            'Dear Sir/Madam,

This is to certify that {{patient_name}} (Patient ID: {{patient_id}}) was treated at our hospital from {{admission_date}} to {{discharge_date}}.

Diagnosis: {{diagnosis}}
Treatment given: {{treatment}}

Wishing a speedy recovery.

Regards,
{{doctor_name}}
{{hospital_name}}',
            1, true, now(), now()
        ),
        (
            gen_random_uuid(),
            'REFERRAL',
            'Referral Letter',
            'Referral - {{patient_name}}',
            'To Whom It May Concern,

Please find referred patient {{patient_name}} (Age: {{age}}, Patient ID: {{patient_id}}) for further evaluation.

Reason for referral: {{reason}}

Thank you,
{{doctor_name}}',
            2, true, now(), now()
        ),
        (
            gen_random_uuid(),
            'FITNESS',
            'Fitness Certificate',
            'Fitness Certificate - {{patient_name}}',
            'This is to certify that Mr/Ms {{patient_name}} has been examined and found fit for {{purpose}}.

Date of examination: {{examination_date}}

{{doctor_name}}
{{hospital_name}}',
            3, true, now(), now()
        )
        """
    )

    op.execute(
        """
        INSERT INTO menus (
            id, code, label, parent_id, sort_order,
            legacy_mcode, legacy_form, parameters, is_active, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            'letter_master',
            'Letter Master',
            parent.id,
            38,
            81,
            'LETTERMSTR',
            NULL,
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'masters'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'letter_master')
        """
    )

    op.execute(
        """
        INSERT INTO role_menu_permissions (
            id, role_id, menu_id, can_view, can_create, can_update, can_delete,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            r.id,
            m.id,
            true, true, true, true,
            now(), now()
        FROM roles r
        CROSS JOIN menus m
        WHERE r.role_name = 'Super Admin'
          AND m.code = 'letter_master'
          AND NOT EXISTS (
              SELECT 1 FROM role_menu_permissions rp
              WHERE rp.role_id = r.id AND rp.menu_id = m.id
          )
        """
    )

    op.execute(
        """
        UPDATE menus
        SET is_active = false,
            updated_at = now()
        WHERE code = 'general_ledger_creation'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE menus
        SET is_active = true,
            updated_at = now()
        WHERE code = 'general_ledger_creation'
        """
    )
    op.execute(
        """
        DELETE FROM role_menu_permissions
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'letter_master')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'letter_master'")
    op.drop_index(op.f("ix_letter_templates_code"), table_name="letter_templates")
    op.drop_table("letter_templates")
