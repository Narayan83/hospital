"""doctor master expansion and departments

Revision ID: 006
Revises: 005
Create Date: 2026-06-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_departments_code"), "departments", ["code"], unique=True)

    op.add_column("doctors", sa.Column("title", sa.String(length=20), nullable=True))
    op.add_column("doctors", sa.Column("second_name", sa.String(length=100), nullable=True))
    op.add_column("doctors", sa.Column("third_name", sa.String(length=100), nullable=True))
    op.add_column("doctors", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("doctors", sa.Column("sex", sa.String(length=10), nullable=True))
    op.add_column("doctors", sa.Column("photo_path", sa.String(length=500), nullable=True))
    op.add_column("doctors", sa.Column("certificate_path", sa.String(length=500), nullable=True))
    op.add_column("doctors", sa.Column("perm_village", sa.String(length=150), nullable=True))
    op.add_column("doctors", sa.Column("perm_post", sa.String(length=150), nullable=True))
    op.add_column("doctors", sa.Column("perm_taluk", sa.String(length=150), nullable=True))
    op.add_column("doctors", sa.Column("perm_district", sa.String(length=150), nullable=True))
    op.add_column("doctors", sa.Column("perm_pincode", sa.String(length=20), nullable=True))
    op.add_column("doctors", sa.Column("temp_village", sa.String(length=150), nullable=True))
    op.add_column("doctors", sa.Column("temp_post", sa.String(length=150), nullable=True))
    op.add_column("doctors", sa.Column("temp_taluk", sa.String(length=150), nullable=True))
    op.add_column("doctors", sa.Column("temp_district", sa.String(length=150), nullable=True))
    op.add_column("doctors", sa.Column("temp_pincode", sa.String(length=20), nullable=True))
    op.add_column("doctors", sa.Column("is_reference_doctor", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("doctors", sa.Column("remarks", sa.Text(), nullable=True))
    op.add_column("doctors", sa.Column("mobile", sa.String(length=20), nullable=True))
    op.add_column("doctors", sa.Column("mobile2", sa.String(length=20), nullable=True))
    op.add_column("doctors", sa.Column("join_date", sa.Date(), nullable=True))
    op.add_column("doctors", sa.Column("department_id", sa.UUID(as_uuid=False), nullable=True))
    op.add_column("doctors", sa.Column("is_existing", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("doctors", sa.Column("release_date", sa.Date(), nullable=True))
    op.add_column("doctors", sa.Column("register_no", sa.String(length=80), nullable=True))
    op.add_column("doctors", sa.Column("morning_token_start", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("doctors", sa.Column("evening_token_start", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("doctors", sa.Column("is_pathology_doctor", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.execute("UPDATE doctors SET second_name = last_name WHERE second_name IS NULL AND last_name IS NOT NULL")
    op.execute("UPDATE doctors SET remarks = notes WHERE remarks IS NULL AND notes IS NOT NULL")

    op.drop_column("doctors", "last_name")
    op.drop_column("doctors", "notes")
    op.create_foreign_key("fk_doctors_department_id", "doctors", "departments", ["department_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_doctors_department_id", "doctors", type_="foreignkey")
    op.drop_column("doctors", "is_pathology_doctor")
    op.drop_column("doctors", "evening_token_start")
    op.drop_column("doctors", "morning_token_start")
    op.drop_column("doctors", "register_no")
    op.drop_column("doctors", "release_date")
    op.drop_column("doctors", "is_existing")
    op.drop_column("doctors", "department_id")
    op.drop_column("doctors", "join_date")
    op.drop_column("doctors", "mobile2")
    op.drop_column("doctors", "mobile")
    op.drop_column("doctors", "remarks")
    op.drop_column("doctors", "is_reference_doctor")
    op.drop_column("doctors", "temp_pincode")
    op.drop_column("doctors", "temp_district")
    op.drop_column("doctors", "temp_taluk")
    op.drop_column("doctors", "temp_post")
    op.drop_column("doctors", "temp_village")
    op.drop_column("doctors", "perm_pincode")
    op.drop_column("doctors", "perm_district")
    op.drop_column("doctors", "perm_taluk")
    op.drop_column("doctors", "perm_post")
    op.drop_column("doctors", "perm_village")
    op.drop_column("doctors", "certificate_path")
    op.drop_column("doctors", "photo_path")
    op.drop_column("doctors", "sex")
    op.drop_column("doctors", "date_of_birth")
    op.drop_column("doctors", "third_name")
    op.drop_column("doctors", "second_name")
    op.drop_column("doctors", "title")
    op.alter_column("doctors", "last_name", existing_type=sa.String(length=100), nullable=False)
    op.drop_index(op.f("ix_departments_code"), table_name="departments")
    op.drop_table("departments")
