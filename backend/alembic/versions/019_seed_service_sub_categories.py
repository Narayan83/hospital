"""seed service sub categories

Revision ID: 019
Revises: 018
Create Date: 2026-06-12

"""
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEEDS = [
    ("GYN", "CONSULT", "Consultation", 1),
    ("GYN", "PROC", "Procedures", 2),
    ("SUR", "MAJOR", "Major Surgery", 1),
    ("SUR", "MINOR", "Minor Surgery", 2),
    ("LAB", "BLOOD", "Blood Tests", 1),
    ("LAB", "URINE", "Urine Tests", 2),
    ("RAD", "XRAY", "X-Ray", 1),
    ("RAD", "USG", "Ultrasound", 2),
    ("GEN", "MISC", "Miscellaneous", 1),
]


def upgrade() -> None:
    conn = op.get_bind()
    for parent_code, code, name, sort_order in SEEDS:
        parent_id = conn.execute(
            sa.text("SELECT id FROM service_categories WHERE code = :code"),
            {"code": parent_code},
        ).scalar()
        if not parent_id:
            continue
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM service_sub_categories WHERE category_id = :cid AND code = :code"
            ),
            {"cid": parent_id, "code": code},
        ).scalar()
        if exists:
            conn.execute(
                sa.text(
                    """
                    UPDATE service_sub_categories
                    SET name = :name, sort_order = :sort_order, is_active = true
                    WHERE category_id = :cid AND code = :code
                    """
                ),
                {"cid": parent_id, "code": code, "name": name, "sort_order": sort_order},
            )
        else:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO service_sub_categories
                    (id, category_id, code, name, sort_order, is_active, created_at, updated_at)
                    VALUES (:id, :cid, :code, :name, :sort_order, true, now(), now())
                    """
                ),
                {
                    "id": str(uuid4()),
                    "cid": parent_id,
                    "code": code,
                    "name": name,
                    "sort_order": sort_order,
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    for parent_code, code, _, _ in SEEDS:
        parent_id = conn.execute(
            sa.text("SELECT id FROM service_categories WHERE code = :code"),
            {"code": parent_code},
        ).scalar()
        if parent_id:
            conn.execute(
                sa.text(
                    "UPDATE service_sub_categories SET is_active = false WHERE category_id = :cid AND code = :code"
                ),
                {"cid": parent_id, "code": code},
            )
