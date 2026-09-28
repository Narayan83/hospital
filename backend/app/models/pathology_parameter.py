from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PathologyParameter(Base, TimestampMixin):
    __tablename__ = "pathology_parameters"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pathology_units.id"), nullable=True
    )
    data_type: Mapped[str] = mapped_column(String(20), default="numeric")
    method: Mapped[str | None] = mapped_column(String(150), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    unit: Mapped["PathologyUnit | None"] = relationship("PathologyUnit")


class PathologyServiceParameter(Base, TimestampMixin):
    __tablename__ = "pathology_service_parameters"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    service_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patient_service_masters.id"), nullable=False, index=True
    )
    parameter_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pathology_parameters.id"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    service: Mapped["PatientServiceMaster"] = relationship("PatientServiceMaster")
    parameter: Mapped["PathologyParameter"] = relationship("PathologyParameter")
