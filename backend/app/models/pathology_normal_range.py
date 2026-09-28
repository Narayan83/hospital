from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PathologyNormalRange(Base, TimestampMixin):
    __tablename__ = "pathology_normal_ranges"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    parameter_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pathology_parameters.id"), nullable=False, index=True
    )
    gender: Mapped[str] = mapped_column(String(1), default="A")
    age_from_days: Mapped[int] = mapped_column(Integer, default=0)
    age_to_days: Mapped[int] = mapped_column(Integer, default=36500)
    min_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    text_range: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pathology_units.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    parameter: Mapped["PathologyParameter"] = relationship("PathologyParameter")
    unit: Mapped["PathologyUnit | None"] = relationship("PathologyUnit")
