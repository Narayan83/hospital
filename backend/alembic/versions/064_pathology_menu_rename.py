"""rename pathology menu labels to clean industry terms

Revision ID: 064
Revises: 063
Create Date: 2026-06-25

"""
from typing import Sequence, Union

from alembic import op

revision: str = "064"
down_revision: Union[str, None] = "063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RENAMES = {
    "service_creation_pathology": "Lab Test Master",
    "unit_creation": "Unit Master",
    "parameter_mapping": "Test Profile / Panel",
    "normal_range_creation": "Reference Ranges",
    "custom_template_creation": "Result Templates",
}


def upgrade() -> None:
    for code, label in _RENAMES.items():
        op.execute(f"UPDATE menus SET label = '{label}' WHERE code = '{code}'")


def downgrade() -> None:
    old = {
        "service_creation_pathology": "Service Creation Pathology",
        "unit_creation": "Unit Creation",
        "parameter_mapping": "Parameter Mapping",
        "normal_range_creation": "Normal Range Creation",
        "custom_template_creation": "Custom Template Creation",
    }
    for code, label in old.items():
        op.execute(f"UPDATE menus SET label = '{label}' WHERE code = '{code}'")
