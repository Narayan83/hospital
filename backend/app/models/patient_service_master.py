from datetime import date
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PatientServiceMaster(Base, TimestampMixin):
    __tablename__ = "patient_service_masters"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    service_charge: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    rate: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    is_sharing: Mapped[bool] = mapped_column(Boolean, default=False)
    doctor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("doctors.id"),
        nullable=True,
    )
    show_in_doctor_collection: Mapped[bool] = mapped_column(Boolean, default=False)
    discount_apply: Mapped[bool] = mapped_column(Boolean, default=False)
    is_renewal: Mapped[bool] = mapped_column(Boolean, default=False)
    renewal_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_service_active: Mapped[bool] = mapped_column(Boolean, default=True)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    category_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("service_categories.id"),
        nullable=True,
    )
    sub_category_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("service_sub_categories.id"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    doctor: Mapped["Doctor | None"] = relationship("Doctor")
    category: Mapped["ServiceCategory | None"] = relationship("ServiceCategory")
    sub_category: Mapped["ServiceSubCategory | None"] = relationship("ServiceSubCategory")
