"""pathology service bundles (service -> service membership) + nested panels

Revision ID: 065
Revises: 064
Create Date: 2026-06-26

Adds a dedicated service->service membership table so a bundle/package can
contain plain tests *and* other bundles (expanded recursively at billing).
Legacy "profiles" (stored as service->foreign-analyte mappings) are migrated
into the new table and those analyte mappings are deactivated, so a bundle no
longer pretends to own analytes of its own.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "065"
down_revision: Union[str, None] = "064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pathology_service_members",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("bundle_service_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("member_service_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bundle_service_id"], ["patient_service_masters.id"]),
        sa.ForeignKeyConstraint(["member_service_id"], ["patient_service_masters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pathology_service_members_bundle_service_id"),
        "pathology_service_members",
        ["bundle_service_id"],
    )
    op.create_index(
        op.f("ix_pathology_service_members_member_service_id"),
        "pathology_service_members",
        ["member_service_id"],
    )

    op.add_column(
        "pathology_bill_lines",
        sa.Column("is_panel_parent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Migrate legacy profiles: a service->analyte mapping where the analyte's code
    # differs from the service's code means the service is really a bundle of the
    # test that owns that analyte.
    op.execute(
        """
        INSERT INTO pathology_service_members (
            id, bundle_service_id, member_service_id, sort_order, is_active, created_at, updated_at
        )
        SELECT gen_random_uuid(), m.service_id, ms.id, m.sort_order, true, now(), now()
        FROM pathology_service_parameters m
        JOIN pathology_parameters p ON p.id = m.parameter_id
        JOIN patient_service_masters s ON s.id = m.service_id
        JOIN patient_service_masters ms ON ms.code = p.code
        WHERE m.is_active = true
          AND p.code <> s.code
          AND NOT EXISTS (
              SELECT 1 FROM pathology_service_members existing
              WHERE existing.bundle_service_id = m.service_id
                AND existing.member_service_id = ms.id
          )
        """
    )

    op.execute(
        """
        UPDATE pathology_service_parameters m
        SET is_active = false
        FROM pathology_parameters p, patient_service_masters s
        WHERE m.parameter_id = p.id
          AND m.service_id = s.id
          AND m.is_active = true
          AND p.code <> s.code
        """
    )


def downgrade() -> None:
    op.drop_column("pathology_bill_lines", "is_panel_parent")
    op.drop_index(
        op.f("ix_pathology_service_members_member_service_id"),
        table_name="pathology_service_members",
    )
    op.drop_index(
        op.f("ix_pathology_service_members_bundle_service_id"),
        table_name="pathology_service_members",
    )
    op.drop_table("pathology_service_members")
