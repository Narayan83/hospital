from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PathologyResultTemplate(Base, TimestampMixin):
    __tablename__ = "pathology_result_templates"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parameter_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("pathology_parameters.id"),
        nullable=True,
        index=True,
    )
    service_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patient_service_masters.id"),
        nullable=True,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    parameter: Mapped["PathologyParameter | None"] = relationship("PathologyParameter")
    service: Mapped["PatientServiceMaster | None"] = relationship("PatientServiceMaster")
