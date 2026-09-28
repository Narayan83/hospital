"""seed patient number formats and menu

Revision ID: 014
Revises: 013
Create Date: 2026-06-11

"""
from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO patient_no_formats (
            id, code, name, pattern, sample_output,
            seq_pad_width, is_selected, sort_order, is_active, created_at, updated_at
        )
        SELECT * FROM (VALUES
            (
                gen_random_uuid(),
                'SECTION_DAILY',
                'Section + Full Date + Daily Seq',
                '{SECTION}{YYYYMMDD}{SEQ:3}',
                'P20260619001',
                3, true, 1, true, now(), now()
            ),
            (
                gen_random_uuid(),
                'PREFIX_DAILY',
                'Prefix + Full Date + Daily Seq',
                '{PREFIX}{YYYYMMDD}{SEQ:3}',
                'P20260619001',
                3, false, 2, true, now(), now()
            ),
            (
                gen_random_uuid(),
                'PREFIX_SHORT_DATE',
                'Prefix + Short Date + Daily Seq',
                '{PREFIX}{YYMMDD}{SEQ:3}',
                'P260619002',
                3, false, 3, true, now(), now()
            ),
            (
                gen_random_uuid(),
                'SIMPLE',
                'Simple Incremental',
                '{SEQ}',
                '1',
                0, false, 4, true, now(), now()
            )
        ) AS v(
            id, code, name, pattern, sample_output,
            seq_pad_width, is_selected, sort_order, is_active, created_at, updated_at
        )
        WHERE NOT EXISTS (SELECT 1 FROM patient_no_formats LIMIT 1)
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
            'patient_id_format',
            'Patient ID Format',
            parent.id,
            48,
            98,
            'CMASTER',
            'PN',
            true,
            now(),
            now()
        FROM menus parent
        WHERE parent.code = 'masters'
          AND NOT EXISTS (SELECT 1 FROM menus WHERE code = 'patient_id_format')
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
          AND m.code = 'patient_id_format'
          AND NOT EXISTS (
              SELECT 1 FROM role_menu_permissions rp
              WHERE rp.role_id = r.id AND rp.menu_id = m.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_menu_permissions
        WHERE menu_id IN (SELECT id FROM menus WHERE code = 'patient_id_format')
        """
    )
    op.execute("DELETE FROM menus WHERE code = 'patient_id_format'")
    op.execute(
        """
        DELETE FROM patient_no_formats
        WHERE code IN (
            'SECTION_DAILY', 'PREFIX_DAILY', 'PREFIX_SHORT_DATE', 'SIMPLE'
        )
        """
    )
