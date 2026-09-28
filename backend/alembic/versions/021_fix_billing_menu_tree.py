"""fix billing menu tree — OPD/IPD under Billing

Revision ID: 021
Revises: 020
Create Date: 2026-06-12

"""
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BILLING_CHILDREN = [
    ("opd_bill", "OPD Bill", 1, 115, "OPBL", None),
    ("ipd_bill", "IPD Bill", 2, None, "IPBL", None),
    ("in_patient_admission", "IPD Admission", 3, 43, None, None),
    ("in_patient_discharge", "IPD Discharge", 4, 44, None, None),
]


def _menu_id(conn, code: str) -> str | None:
    row = conn.execute(sa.text("SELECT id FROM menus WHERE code = :code"), {"code": code}).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()
    billing_id = _menu_id(conn, "billing")
    transactions_id = _menu_id(conn, "transactions")
    if not billing_id or not transactions_id:
        return

    conn.execute(
        sa.text(
            "UPDATE menus SET parent_id = :transactions_id, sort_order = 1, label = 'Billing' "
            "WHERE code = 'billing'"
        ),
        {"transactions_id": transactions_id},
    )

    for code, label, sort_order, legacy_mcode, legacy_form, parameters in BILLING_CHILDREN:
        menu_id = _menu_id(conn, code)
        if menu_id:
            conn.execute(
                sa.text(
                    """
                    UPDATE menus
                    SET parent_id = :billing_id,
                        label = :label,
                        sort_order = :sort_order,
                        legacy_mcode = :legacy_mcode,
                        legacy_form = :legacy_form,
                        parameters = :parameters,
                        is_active = true
                    WHERE code = :code
                    """
                ),
                {
                    "billing_id": billing_id,
                    "code": code,
                    "label": label,
                    "sort_order": sort_order,
                    "legacy_mcode": legacy_mcode,
                    "legacy_form": legacy_form,
                    "parameters": parameters,
                },
            )
        else:
            new_id = str(uuid4())
            conn.execute(
                sa.text(
                    """
                    INSERT INTO menus (
                        id, code, label, parent_id, sort_order,
                        legacy_mcode, legacy_form, parameters, is_active,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :code, :label, :billing_id, :sort_order,
                        :legacy_mcode, :legacy_form, :parameters, true,
                        now(), now()
                    )
                    """
                ),
                {
                    "id": new_id,
                    "code": code,
                    "label": label,
                    "billing_id": billing_id,
                    "sort_order": sort_order,
                    "legacy_mcode": legacy_mcode,
                    "legacy_form": legacy_form,
                    "parameters": parameters,
                },
            )

    opd_id = _menu_id(conn, "opd_bill")
    role_rows = conn.execute(
        sa.text(
            """
            SELECT DISTINCT role_id, can_view, can_create, can_update, can_delete
            FROM role_menu_permissions
            WHERE menu_id = :opd_id
            """
        ),
        {"opd_id": opd_id},
    ).fetchall() if opd_id else []

    super_admin = conn.execute(
        sa.text("SELECT id FROM roles WHERE role_name = 'Super Admin'")
    ).fetchone()
    role_grants: dict[str, tuple] = {row[0]: row[1:] for row in role_rows}
    if super_admin:
        role_grants[super_admin[0]] = (True, True, True, True)

    for code, *_ in BILLING_CHILDREN:
        menu_id = _menu_id(conn, code)
        if not menu_id:
            continue
        for role_id, (can_view, can_create, can_update, can_delete) in role_grants.items():
            exists = conn.execute(
                sa.text(
                    "SELECT 1 FROM role_menu_permissions WHERE role_id = :role_id AND menu_id = :menu_id"
                ),
                {"role_id": role_id, "menu_id": menu_id},
            ).fetchone()
            if exists:
                continue
            conn.execute(
                sa.text(
                    """
                    INSERT INTO role_menu_permissions (
                        id, role_id, menu_id,
                        can_view, can_create, can_update, can_delete,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :role_id, :menu_id,
                        :can_view, :can_create, :can_update, :can_delete,
                        now(), now()
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "role_id": role_id,
                    "menu_id": menu_id,
                    "can_view": can_view,
                    "can_create": can_create,
                    "can_update": can_update,
                    "can_delete": can_delete,
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    transactions_id = _menu_id(conn, "transactions")
    ward_id = _menu_id(conn, "ward_management")
    if transactions_id:
        conn.execute(
            sa.text("UPDATE menus SET parent_id = :pid WHERE code = 'opd_bill'"),
            {"pid": transactions_id},
        )
    if ward_id:
        conn.execute(
            sa.text(
                "UPDATE menus SET parent_id = :pid WHERE code IN "
                "('in_patient_admission', 'in_patient_discharge')"
            ),
            {"pid": ward_id},
        )
    conn.execute(sa.text("UPDATE menus SET is_active = false WHERE code = 'ipd_bill'"))
