"""seed service categories

Revision ID: 017
Revises: 016
Create Date: 2026-06-12

"""
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORIES = [
    ("GYN", "Gynecology", 1),
    ("SUR", "Surgery", 2),
    ("LAB", "Laboratory", 3),
    ("RAD", "Radiology", 4),
    ("GEN", "General", 5),
]


def upgrade() -> None:
    conn = op.get_bind()
    for code, name, sort_order in CATEGORIES:
        exists = conn.execute(
            sa.text("SELECT 1 FROM service_categories WHERE code = :code"),
            {"code": code},
        ).scalar()
        if exists:
            conn.execute(
                sa.text(
                    """
                    UPDATE service_categories
                    SET name = :name, sort_order = :sort_order, is_active = true
                    WHERE code = :code
                    """
                ),
                {"code": code, "name": name, "sort_order": sort_order},
            )
        else:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO service_categories
                    (id, code, name, sort_order, is_active, created_at, updated_at)
                    VALUES (:id, :code, :name, :sort_order, true, now(), now())
                    """
                ),
                {"id": str(uuid4()), "code": code, "name": name, "sort_order": sort_order},
            )


def downgrade() -> None:
    conn = op.get_bind()
    for code, _, _ in CATEGORIES:
        conn.execute(
            sa.text("UPDATE service_categories SET is_active = false WHERE code = :code"),
            {"code": code},
        )
