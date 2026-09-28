from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class BillingStructureMapping(Base, TimestampMixin):
    __tablename__ = "billing_structure_mappings"
    __table_args__ = (
        UniqueConstraint(
            "billing_type_id",
            "department_id",
            "procedure_type_id",
            name="uq_billing_structure_combo",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    billing_type_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("billing_types.id"), nullable=False, index=True
    )
    department_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("departments.id"), nullable=False, index=True
    )
    procedure_type_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("procedure_types.id"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
