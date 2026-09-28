from datetime import date
from uuid import uuid4

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ShortBillType(Base, TimestampMixin):
    """Master — one row per short bill menu (Scan, XRay, Observation, etc.)."""

    __tablename__ = "short_bill_types"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    menu_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    default_service_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patient_service_masters.id"), nullable=True
    )
    default_service_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    default_rate: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    default_doctor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=True
    )
    bill_prefix: Mapped[str] = mapped_column(String(20), default="SB")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    default_service: Mapped["PatientServiceMaster | None"] = relationship("PatientServiceMaster")
    default_doctor: Mapped["Doctor | None"] = relationship("Doctor")


class ShortBill(Base, TimestampMixin):
    __tablename__ = "short_bills"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    bill_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False)
    short_bill_type_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("short_bill_types.id"), nullable=False, index=True
    )
    patient_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("patients.id"), nullable=True, index=True
    )
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    service_name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    doctor_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("doctors.id"), nullable=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    bill_type: Mapped["ShortBillType"] = relationship("ShortBillType")
    patient: Mapped["Patient | None"] = relationship("Patient")
    doctor: Mapped["Doctor | None"] = relationship("Doctor")
